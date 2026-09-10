# Persistence Memory

## Current state

SQLAlchemy async models and Alembic migrations through `20260909_0003` cover
reviews, findings/questions, interviews/turns, progress snapshots, knowledge
items, retrieval events, and complete agent-run diagnostics. Provenance, output
origins, corpus hashes/versions, seeded/active flags, prompt versions, tokens,
cost, latency, retries, and safe failure categories are durable. Runtime
repositories reuse one engine/session factory and FastAPI closes it on shutdown.

The schema deliberately has no `code`, `raw_code`, `source_code`, or `evidence`
column. Reviews store SHA-256 + line count; interview answers store SHA-256 + a
derived signal summary.

## Decisions

- Pydantic persistence records sit between application and ORM models.
- ECS injects only the `password` JSON field from the RDS-managed secret; the
  app URL-encodes credentials while building the async URL in memory.
- Migrations are a one-off deployment task, never an every-replica startup.
- Neon runtime uses the pooled `DATABASE_URL`; Alembic and administrative seed
  work use `DIRECT_DATABASE_URL`.

## Production evidence

Neon project `holy-feather-79203801`, branch `production`, is at Alembic head
with all ten tables, exactly 120 active sourced 1536-dimensional seed rows, no
raw-code/raw-answer columns, and a passing pooled temporary read/write. Snapshot
`clutch-pre-migration-20260910` predates the schema change.

## Known gaps

- Add retention/deletion jobs and migration rollback rehearsal before public
  production use.
