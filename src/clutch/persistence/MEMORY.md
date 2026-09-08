# Persistence Memory

## Current state

SQLAlchemy async models and Alembic migrations through `20260908_0002` cover
reviews, findings/questions, interviews/turns, progress snapshots, knowledge
items, retrieval events, and agent runs. The second migration adds knowledge
item type, roles, and seniority metadata with safe backfill defaults. Factories
choose PostgreSQL only when a full `DATABASE_URL` or secret-friendly
`CLUTCH_DB_*` components are configured.

The schema deliberately has no `code`, `raw_code`, `source_code`, or `evidence`
column. Reviews store SHA-256 + line count; interview answers store SHA-256 + a
derived signal summary.

## Decisions

- Pydantic persistence records sit between application and ORM models.
- ECS injects only the `password` JSON field from the RDS-managed secret; the
  app URL-encodes credentials while building the async URL in memory.
- Migrations are a one-off deployment task, never an every-replica startup.

## Known gaps

- Add retention/deletion jobs and migration rollback rehearsal before public
  production use.
