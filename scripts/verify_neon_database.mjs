/** Verify Clutch's Neon schema and seed over Neon's HTTPS SQL transport. */

import { neon } from "@neondatabase/serverless";

const EXPECTED_TABLES = [
  "agent_runs",
  "alembic_version",
  "generated_questions",
  "interview_sessions",
  "interview_turns",
  "knowledge_base_items",
  "progress_snapshots",
  "retrieval_events",
  "review_findings",
  "review_sessions",
];
const FORBIDDEN_RAW_COLUMNS = [
  "answer",
  "answer_text",
  "code",
  "raw_answer",
  "raw_code",
  "source_code",
];

const requireSeeded = process.argv.includes("--require-seeded");
const runtime = process.argv.includes("--runtime");
const databaseUrl = runtime
  ? process.env.DATABASE_URL
  : process.env.DIRECT_DATABASE_URL;
if (!databaseUrl) {
  throw new Error(`${runtime ? "DATABASE_URL" : "DIRECT_DATABASE_URL"} is required`);
}

const sql = neon(databaseUrl);
const [metadata] = await sql`
  SELECT current_database() AS database_name,
         current_setting('server_version_num')::integer / 10000 AS postgres_major
`;
const tables = (
  await sql`
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
  `
).map((row) => row.table_name);
const tableSet = new Set(tables);

let migrationRevision = null;
let activeSeededItems = 0;
let validProvenanceItems = 0;
let validEmbeddingItems = 0;
if (tableSet.has("alembic_version")) {
  const [revision] = await sql`SELECT version_num FROM alembic_version`;
  migrationRevision = revision?.version_num ?? null;
}
if (tableSet.has("knowledge_base_items")) {
  const [counts] = await sql`
    SELECT
      count(*) FILTER (WHERE is_seeded AND is_active)::integer
        AS active_seeded_items,
      count(*) FILTER (
        WHERE is_seeded AND is_active
          AND url IS NOT NULL AND url <> ''
          AND source_family IS NOT NULL
          AND section_locator IS NOT NULL
          AND corpus_version IS NOT NULL
          AND content_sha256 IS NOT NULL
      )::integer AS valid_provenance_items,
      count(*) FILTER (
        WHERE is_seeded AND is_active
          AND embedding IS NOT NULL
          AND vector_dims(embedding) = 1536
      )::integer AS valid_embedding_items
    FROM knowledge_base_items
  `;
  activeSeededItems = counts.active_seeded_items;
  validProvenanceItems = counts.valid_provenance_items;
  validEmbeddingItems = counts.valid_embedding_items;
}

const rawColumns = (
  await sql`
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND column_name = ANY(${FORBIDDEN_RAW_COLUMNS})
    ORDER BY table_name, column_name
  `
).map((row) => `${row.table_name}.${row.column_name}`);

let runtimeSmokePassed = true;
if (runtime) {
  const [, , rows] = await sql.transaction((txn) => [
    txn`CREATE TEMP TABLE clutch_runtime_smoke (value integer)`,
    txn`INSERT INTO clutch_runtime_smoke (value) VALUES (1)`,
    txn`SELECT value FROM clutch_runtime_smoke`,
  ]);
  runtimeSmokePassed = rows[0]?.value === 1;
}

const result = {
  active_seeded_items: activeSeededItems,
  database_name: metadata.database_name,
  forbidden_raw_columns: rawColumns,
  migration_revision: migrationRevision,
  missing_tables: EXPECTED_TABLES.filter((table) => !tableSet.has(table)),
  postgres_major: metadata.postgres_major,
  runtime_smoke_passed: runtimeSmokePassed,
  tables,
  valid_embedding_items: validEmbeddingItems,
  valid_provenance_items: validProvenanceItems,
};
console.log(JSON.stringify(result, null, 2));

const schemaPasses =
  result.missing_tables.length === 0 &&
  result.migration_revision === "20260909_0003" &&
  result.forbidden_raw_columns.length === 0 &&
  result.runtime_smoke_passed;
const seedPasses =
  !requireSeeded ||
  (result.active_seeded_items === 120 &&
    result.valid_provenance_items === 120 &&
    result.valid_embedding_items === 120);
if (!schemaPasses || !seedPasses) process.exitCode = 1;
