# Knowledge Base Memory

## Current state

The committed `corpus.json` contains exactly 120 atomic items across all six
finding categories: 72 references, 18 rubrics, and 30 question-bank prompts,
with 20 items per category. Every item has a stable ID, exact anchored URL,
source family/title/section, corpus version, content SHA-256, item type, role and
seniority tags, plus validated derivation IDs where applicable. Sources are
restricted to Python docs/PEPs, OWASP Cheat Sheets, pytest/unittest docs, Google
Engineering Practices, and the Google Python style guide.

`src/clutch/rag/retrieval.py` provides:

- deterministic in-memory lexical retrieval;
- PostgreSQL full-text ranking;
- optional OpenAI embeddings + pgvector cosine distance;
- reciprocal-rank-style score fusion and local fallback;
- Redis wrappers for hashed retrieval results and embeddings.

Alembic creates FTS plus 1536-dimensional HNSW vector indexes. Migration
`20260909_0003` adds provenance, content hashes, active/seeded status, and model
diagnostics. Seeding is a versioned synchronization: insert/update/re-embed,
deactivate obsolete seed rows, and preserve unrelated data.

## Decisions

- Retrieval remains internal; only GitHub belongs behind MCP.
- No OpenAI key means lexical PostgreSQL retrieval, not a broken vector path.
- Cache values contain knowledge-base material only; raw code/review evidence is
  excluded and keys contain SHA-256 digests.

## Known gaps

- Neon production has 120 active sourced rows and 120 valid embeddings. The
  production comparison measured all four strategies; local lexical is the only
  current gate-passing default. Improve Neon hybrid mappings/ranking before
  switching rather than lowering thresholds.
