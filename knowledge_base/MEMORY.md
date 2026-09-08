# Knowledge Base Memory

## Current state

The committed `corpus.json` contains 60 validated items across all six finding
categories: 36 cited references plus 12 interview rubrics and 12 question-bank
prompts. Every item has a stable ID, citation, item type, role tags, and
seniority levels. Package data is validated at import; duplicate IDs or citation
ID mismatches fail fast.

`src/clutch/rag/retrieval.py` provides:

- deterministic in-memory lexical retrieval;
- PostgreSQL full-text ranking;
- optional OpenAI embeddings + pgvector cosine distance;
- reciprocal-rank-style score fusion and local fallback;
- Redis wrappers for hashed retrieval results and embeddings.

Alembic seeds the durable corpus and creates FTS plus 1536-dimensional HNSW
vector indexes. Migration `20260908_0002` adds item type, roles, and seniority
metadata to existing databases.

## Decisions

- Retrieval remains internal; only GitHub belongs behind MCP.
- No OpenAI key means lexical PostgreSQL retrieval, not a broken vector path.
- Cache values contain knowledge-base material only; raw code/review evidence is
  excluded and keys contain SHA-256 digests.

## Known gaps

- Expand from 60 to the planned 100–500 role/rubric/question items without
  duplicating near-identical text.
- Capture vector-only vs hybrid quality/latency/cost on the same expanded eval
  set; current deterministic fixtures are too small to justify reranking.
