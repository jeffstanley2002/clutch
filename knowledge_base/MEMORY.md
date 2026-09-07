# Knowledge Base Memory

## Current State

`src/clutch/knowledge_base` contains the first seeded clean-code corpus and a
deterministic retrieval interface.

Current corpus:

- Explicit incomplete work.
- Intentional boundary observability.
- Narrow error handling.
- Safe Python defaults.
- Small reviewable units.
- Behavioral test boundaries.

## Decisions

- Retrieval is local and lexical for Day 3 so `/review` remains fully runnable
  without a database, embeddings, or model calls.
- Each principle is a Pydantic model with an embedded `Citation`, so findings
  can be grounded through the same structured citation shape the API already
  returns.
- This is the stable interface that later vector or hybrid retrieval can
  replace internally.

## Known Gaps

- No embeddings, pgvector storage, BM25, or reranking yet.
- The corpus is intentionally tiny and should grow during Phase 2.
