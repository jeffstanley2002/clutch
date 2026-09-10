/** Measure local lexical and Neon lexical/vector/hybrid retrieval consistently. */

import { performance } from "node:perf_hooks";
import { neon } from "@neondatabase/serverless";

const K = 3;
const DEBUG_IDS = process.argv.includes("--debug-ids");
const MODEL = process.env.OPENAI_EMBEDDING_MODEL || "text-embedding-3-small";
const PRICE_PER_MILLION_USD = Number(
  process.env.CLUTCH_EMBEDDING_PRICE_PER_MILLION_USD || 0.02,
);
const GATES = {
  irrelevant_at_3_max: 0.15,
  judgment_coverage_at_3_min: 0.9,
  mrr_min: 1.0,
  ndcg_at_3_min: 0.9,
  recall_at_3_min: 0.55,
};

function lexicalQuery(query) {
  const terms = [...new Set(query.toLowerCase().match(/[a-z0-9_]+/g) || [])];
  return terms.slice(0, 64).join(" OR ") || "clutch";
}

function dcg(grades) {
  return grades.reduce(
    (total, grade, index) => total + (2 ** grade - 1) / Math.log2(index + 2),
    0,
  );
}

function caseMetrics(caseId, ids, judgments, latencyMs) {
  const grades = ids.map((id) => judgments[id] ?? 0);
  const relevantRanks = grades
    .map((grade, index) => (grade >= 2 ? index + 1 : null))
    .filter(Boolean);
  const ideal = Object.values(judgments)
    .sort((left, right) => right - left)
    .slice(0, K);
  const metrics = {
    case_id: caseId,
    irrelevant_retrieved: grades.filter((grade) => grade === 0).length,
    judged_retrieved: ids.filter((id) => Object.hasOwn(judgments, id)).length,
    latency_ms: latencyMs,
    ndcg_at_3: ideal.length ? dcg(grades) / dcg(ideal) : 0,
    reciprocal_rank: relevantRanks.length ? 1 / relevantRanks[0] : 0,
    relevant_retrieved: grades.filter((grade) => grade >= 2).length,
    relevant_total: Object.values(judgments).filter((grade) => grade >= 2).length,
    returned: ids.length,
  };
  if (DEBUG_IDS) metrics.retrieved_ids = ids;
  return metrics;
}

function summarize(strategy, cases, estimatedCostUsd) {
  const evaluated = cases.filter((item) => item.relevant_total > 0);
  const relevantRetrieved = evaluated.reduce(
    (total, item) => total + item.relevant_retrieved,
    0,
  );
  const relevantTotal = evaluated.reduce(
    (total, item) => total + item.relevant_total,
    0,
  );
  const returnedEvaluated = evaluated.reduce(
    (total, item) => total + item.returned,
    0,
  );
  const returned = cases.reduce((total, item) => total + item.returned, 0);
  const ratio = (numerator, denominator) =>
    denominator ? numerator / denominator : 0;
  const report = {
    average_latency_ms: ratio(
      cases.reduce((total, item) => total + item.latency_ms, 0),
      cases.length,
    ),
    case_count: cases.length,
    estimated_query_cost_usd: estimatedCostUsd,
    irrelevant_at_3: ratio(
      cases.reduce((total, item) => total + item.irrelevant_retrieved, 0),
      returned,
    ),
    judgment_coverage_at_3: ratio(
      cases.reduce((total, item) => total + item.judged_retrieved, 0),
      returned,
    ),
    mrr: ratio(
      evaluated.reduce((total, item) => total + item.reciprocal_rank, 0),
      evaluated.length,
    ),
    ndcg_at_3: ratio(
      cases.reduce((total, item) => total + item.ndcg_at_3, 0),
      cases.length,
    ),
    precision_at_3: ratio(relevantRetrieved, returnedEvaluated),
    recall_at_3: ratio(relevantRetrieved, relevantTotal),
    strategy,
  };
  report.meets_current_gate =
    report.recall_at_3 >= GATES.recall_at_3_min &&
    report.mrr >= GATES.mrr_min &&
    report.ndcg_at_3 >= GATES.ndcg_at_3_min &&
    report.judgment_coverage_at_3 >= GATES.judgment_coverage_at_3_min &&
    report.irrelevant_at_3 <= GATES.irrelevant_at_3_max;
  report.cases = cases.map(({ case_id, ...metrics }) => ({ case_id, ...metrics }));
  return report;
}

async function embedQueries(queries) {
  const response = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dimensions: 1536,
      encoding_format: "float",
      input: queries,
      model: MODEL,
    }),
  });
  if (!response.ok) {
    throw new Error(`Embedding request failed with HTTP ${response.status}`);
  }
  const payload = await response.json();
  return {
    tokens: payload.usage?.total_tokens ?? 0,
    vectors: [...payload.data]
      .sort((left, right) => left.index - right.index)
      .map((entry) => entry.embedding),
  };
}

if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is required");
if (!process.env.OPENAI_API_KEY) throw new Error("OPENAI_API_KEY is required");
let benchmarkInput = "";
for await (const chunk of process.stdin) benchmarkInput += chunk;
const benchmark = JSON.parse(benchmarkInput);
const embedded = await embedQueries(benchmark.cases.map((item) => item.query));
const sql = neon(process.env.DATABASE_URL);
const results = {
  local_lexical: [],
  postgres_hybrid: [],
  postgres_lexical: [],
  postgres_vector: [],
};

for (const [index, item] of benchmark.cases.entries()) {
  results.local_lexical.push(
    caseMetrics(
      item.case_id,
      item.local_ids,
      item.judgments,
      item.local_latency_ms,
    ),
  );
  const categories = item.categories;
  const websearch = lexicalQuery(item.query);
  const vector = JSON.stringify(embedded.vectors[index]);

  let startedAt = performance.now();
  const lexicalRows = await sql`
    SELECT source_id,
           ts_rank_cd(
             to_tsvector('english', search_text),
             websearch_to_tsquery('english', ${websearch})
           ) AS lexical_rank
    FROM knowledge_base_items
    WHERE is_active AND is_seeded
      AND (
        cardinality(${categories}::text[]) = 0
        OR category = ANY(${categories}::text[])
      )
      AND ts_rank_cd(
        to_tsvector('english', search_text),
        websearch_to_tsquery('english', ${websearch})
      ) > 0
    ORDER BY lexical_rank DESC, source_id
    LIMIT 3
  `;
  results.postgres_lexical.push(
    caseMetrics(
      item.case_id,
      lexicalRows.map((row) => row.source_id),
      item.judgments,
      performance.now() - startedAt,
    ),
  );

  startedAt = performance.now();
  const vectorRows = await sql`
    SELECT source_id
    FROM knowledge_base_items
    WHERE is_active AND is_seeded AND embedding IS NOT NULL
      AND (
        cardinality(${categories}::text[]) = 0
        OR category = ANY(${categories}::text[])
      )
    ORDER BY embedding <=> ${vector}::vector, source_id
    LIMIT 3
  `;
  results.postgres_vector.push(
    caseMetrics(
      item.case_id,
      vectorRows.map((row) => row.source_id),
      item.judgments,
      performance.now() - startedAt,
    ),
  );

  startedAt = performance.now();
  const hybridRows = await sql`
    SELECT source_id,
           ts_rank_cd(
             to_tsvector('english', search_text),
             websearch_to_tsquery('english', ${websearch})
           ) AS lexical_rank,
           embedding <=> ${vector}::vector AS vector_distance
    FROM knowledge_base_items
    WHERE is_active AND is_seeded
      AND (
        cardinality(${categories}::text[]) = 0
        OR category = ANY(${categories}::text[])
      )
      AND (
        ts_rank_cd(
          to_tsvector('english', search_text),
          websearch_to_tsquery('english', ${websearch})
        ) > 0
        OR embedding IS NOT NULL
      )
    ORDER BY lexical_rank DESC, vector_distance, source_id
    LIMIT 12
  `;
  const hybridIds = hybridRows
    .map((row) => {
      const lexicalRank = Number(row.lexical_rank || 0);
      const semanticScore = Math.max(
        0,
        Math.min(1, 1 - Number(row.vector_distance)),
      );
      return {
        id: row.source_id,
        score: 0.45 * (lexicalRank / (1 + lexicalRank)) + 0.55 * semanticScore,
      };
    })
    .sort((left, right) => right.score - left.score || left.id.localeCompare(right.id))
    .slice(0, K)
    .map((candidate) => candidate.id);
  results.postgres_hybrid.push(
    caseMetrics(
      item.case_id,
      hybridIds,
      item.judgments,
      performance.now() - startedAt,
    ),
  );
}

const queryCost = (embedded.tokens / 1_000_000) * PRICE_PER_MILLION_USD;
const strategies = [
  summarize("local_lexical", results.local_lexical, 0),
  summarize("postgres_lexical", results.postgres_lexical, 0),
  summarize("postgres_vector", results.postgres_vector, queryCost),
  summarize("postgres_hybrid", results.postgres_hybrid, queryCost),
];
const passing = strategies.filter((strategy) => strategy.meets_current_gate);
passing.sort(
  (left, right) =>
    right.ndcg_at_3 - left.ndcg_at_3 ||
    right.recall_at_3 - left.recall_at_3 ||
    left.estimated_query_cost_usd - right.estimated_query_cost_usd ||
    left.average_latency_ms - right.average_latency_ms,
);
const report = {
  corpus_size: 120,
  database_transport: "neon_https",
  dataset_version: benchmark.dataset_version,
  embedding_model: MODEL,
  embedding_query_cost_usd: queryCost,
  embedding_query_tokens: embedded.tokens,
  gates: GATES,
  k: K,
  measured_at: new Date().toISOString(),
  selected_default: passing[0]?.strategy ?? null,
  strategies,
};
console.log(JSON.stringify(report, null, 2));
if (!report.selected_default) process.exitCode = 1;
