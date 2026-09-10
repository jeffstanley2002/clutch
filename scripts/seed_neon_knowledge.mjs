/** Synchronize Clutch's public corpus and embeddings to Neon over HTTPS. */

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { neon } from "@neondatabase/serverless";

const CORPUS_PATH = new URL("../src/clutch/knowledge_base/corpus.json", import.meta.url);
const EXPECTED_CORPUS_SIZE = 120;
const EMBEDDING_DIMENSIONS = 1536;
const DEFAULT_MODEL = "text-embedding-3-small";
const DEFAULT_PRICE_PER_MILLION_USD = 0.02;
const DEFAULT_MAX_COST_USD = 0.01;

function buildSearchText(item) {
  return [
    item.id,
    item.title,
    item.summary,
    item.guidance,
    item.item_type,
    item.roles.join(" "),
    item.seniority_levels.join(" "),
    item.tags.join(" "),
  ].join(" ");
}

function validateCorpus(corpus) {
  if (!Array.isArray(corpus) || corpus.length !== EXPECTED_CORPUS_SIZE) {
    throw new Error(`Expected exactly ${EXPECTED_CORPUS_SIZE} corpus items`);
  }
  const ids = new Set();
  for (const item of corpus) {
    if (!item.id || ids.has(item.id)) throw new Error("Corpus IDs must be unique");
    ids.add(item.id);
    if (!item.citation?.url || !item.citation?.title || !item.section_locator) {
      throw new Error(`Corpus item ${item.id} lacks exact provenance`);
    }
    const contentHash = createHash("sha256")
      .update(`${item.summary}\n${item.guidance}`)
      .digest("hex");
    if (contentHash !== item.content_sha256) {
      throw new Error(`Corpus item ${item.id} has a stale content hash`);
    }
  }
}

async function embedBatch(texts, { apiKey, model }) {
  const response = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dimensions: EMBEDDING_DIMENSIONS,
      encoding_format: "float",
      input: texts,
      model,
    }),
  });
  if (!response.ok) {
    throw new Error(`Embedding request failed with HTTP ${response.status}`);
  }
  const payload = await response.json();
  const vectors = [...payload.data]
    .sort((left, right) => left.index - right.index)
    .map((entry) => entry.embedding);
  if (
    vectors.length !== texts.length ||
    vectors.some((vector) => vector.length !== EMBEDDING_DIMENSIONS)
  ) {
    throw new Error("Embedding response does not match the 1536-dimensional schema");
  }
  return { tokens: payload.usage?.total_tokens ?? 0, vectors };
}

if (!process.env.DIRECT_DATABASE_URL) {
  throw new Error("DIRECT_DATABASE_URL is required");
}
if (!process.env.OPENAI_API_KEY) throw new Error("OPENAI_API_KEY is required");

const model = process.env.OPENAI_EMBEDDING_MODEL || DEFAULT_MODEL;
const pricePerMillion = Number(
  process.env.CLUTCH_EMBEDDING_USD_PER_MILLION ||
    DEFAULT_PRICE_PER_MILLION_USD,
);
const maxCost = Number(
  process.env.CLUTCH_SEED_MAX_COST_USD || DEFAULT_MAX_COST_USD,
);
if (![pricePerMillion, maxCost].every(Number.isFinite)) {
  throw new Error("Embedding cost limits must be finite numbers");
}

const corpus = JSON.parse(await readFile(CORPUS_PATH, "utf8"));
validateCorpus(corpus);
const sql = neon(process.env.DIRECT_DATABASE_URL);
const existingRows = await sql`
  SELECT source_id, content_sha256, embedding_model,
         embedding IS NOT NULL AS has_embedding
  FROM knowledge_base_items
  WHERE is_seeded OR source_id = ANY(${corpus.map((item) => item.id)})
`;
const existingById = new Map(existingRows.map((row) => [row.source_id, row]));
const targets = corpus.filter((item) => {
  const existing = existingById.get(item.id);
  return (
    !existing ||
    !existing.has_embedding ||
    existing.content_sha256 !== item.content_sha256 ||
    existing.embedding_model !== model
  );
});

const estimatedTokens = Math.ceil(
  targets.reduce((total, item) => total + buildSearchText(item).length, 0) / 4,
);
const estimatedCost = (estimatedTokens / 1_000_000) * pricePerMillion;
if (estimatedCost > maxCost) {
  throw new Error(
    `Estimated embedding cost $${estimatedCost.toFixed(6)} exceeds seed cap`,
  );
}

const embeddingsById = new Map();
let embeddingTokens = 0;
const embeddingBatchSize = 64;
for (let index = 0; index < targets.length; index += embeddingBatchSize) {
  const batch = targets.slice(index, index + embeddingBatchSize);
  const embedded = await embedBatch(batch.map(buildSearchText), {
    apiKey: process.env.OPENAI_API_KEY,
    model,
  });
  embeddingTokens += embedded.tokens;
  batch.forEach((item, offset) => {
    embeddingsById.set(item.id, embedded.vectors[offset]);
  });
}

const upserts = corpus.map((item) => {
  const existing = existingById.get(item.id);
  const embedding = embeddingsById.get(item.id);
  const embeddingLiteral = embedding ? JSON.stringify(embedding) : null;
  return sql`
    INSERT INTO knowledge_base_items (
      source_id, title, category, item_type, roles, seniority_levels,
      principle, rationale, interview_signal, tags, url, search_text,
      source_family, source_title, section_locator, corpus_version,
      content_sha256, derived_from_ids, is_active, is_seeded,
      embedding_model, embedding
    ) VALUES (
      ${item.id}, ${item.title}, ${item.category}, ${item.item_type},
      ${JSON.stringify(item.roles)}::jsonb,
      ${JSON.stringify(item.seniority_levels)}::jsonb,
      ${item.summary}, ${item.guidance}, ${item.guidance},
      ${JSON.stringify(item.tags)}::jsonb,
      ${item.citation.url}, ${buildSearchText(item)}, ${item.source_family},
      ${item.citation.title}, ${item.section_locator}, ${item.corpus_version},
      ${item.content_sha256}, ${JSON.stringify(item.derived_from_ids)}::jsonb,
      true, true, ${embedding ? model : existing?.embedding_model ?? null},
      CASE
        WHEN ${embeddingLiteral}::text IS NULL THEN NULL
        ELSE ${embeddingLiteral}::vector
      END
    )
    ON CONFLICT (source_id) DO UPDATE SET
      title = EXCLUDED.title,
      category = EXCLUDED.category,
      item_type = EXCLUDED.item_type,
      roles = EXCLUDED.roles,
      seniority_levels = EXCLUDED.seniority_levels,
      principle = EXCLUDED.principle,
      rationale = EXCLUDED.rationale,
      interview_signal = EXCLUDED.interview_signal,
      tags = EXCLUDED.tags,
      url = EXCLUDED.url,
      search_text = EXCLUDED.search_text,
      source_family = EXCLUDED.source_family,
      source_title = EXCLUDED.source_title,
      section_locator = EXCLUDED.section_locator,
      corpus_version = EXCLUDED.corpus_version,
      content_sha256 = EXCLUDED.content_sha256,
      derived_from_ids = EXCLUDED.derived_from_ids,
      is_active = true,
      is_seeded = true,
      embedding_model = COALESCE(EXCLUDED.embedding_model, knowledge_base_items.embedding_model),
      embedding = COALESCE(EXCLUDED.embedding, knowledge_base_items.embedding),
      updated_at = now()
  `;
});
const activeIds = corpus.map((item) => item.id);
const transactionResults = await sql.transaction([
  ...upserts,
  sql`
    UPDATE knowledge_base_items
    SET is_active = false, updated_at = now()
    WHERE is_seeded AND NOT (source_id = ANY(${activeIds}))
    RETURNING source_id
  `,
]);
const deactivated = transactionResults.at(-1).length;
const inserted = corpus.filter((item) => !existingById.has(item.id)).length;
const updated = corpus.filter((item) => {
  const existing = existingById.get(item.id);
  return existing && targets.some((target) => target.id === item.id);
}).length;
const reembedded = targets.length;
const unchanged = corpus.length - inserted - updated;
const actualCost = (embeddingTokens / 1_000_000) * pricePerMillion;

console.log(
  JSON.stringify({
    corpus_version: corpus[0].corpus_version,
    deactivated,
    embedding_cost_usd: Number(actualCost.toFixed(8)),
    embedding_model: model,
    embedding_tokens: embeddingTokens,
    inserted,
    reembedded,
    unchanged,
    updated,
  }),
);
