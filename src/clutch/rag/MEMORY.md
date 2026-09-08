# RAG Memory

## Current state

Retrieval supports local lexical search and durable PostgreSQL hybrid search.
PostgreSQL combines full-text rank with optional 1536-dimensional OpenAI
embedding distance; local fallback preserves availability. Redis wrappers cache
only hashed queries/vectors and knowledge-base results. The validated corpus has
60 references/rubrics/question prompts with explicit item type, role, and
seniority metadata; those fields participate in lexical search and survive the
SQL round trip.

## Decisions

- Embedding absence degrades to lexical retrieval.
- Cache/provider/database failure must not block review.
- Citation IDs remain stable across local and SQL paths.

## Known gaps

- No semantic reranker and no credible vector-vs-hybrid comparison until the
  corpus reaches at least 100 items and multi-file eval coverage exists.
