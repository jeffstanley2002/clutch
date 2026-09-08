# RAG Memory

## Current state

Retrieval supports local lexical search and durable PostgreSQL hybrid search.
PostgreSQL combines full-text rank with optional 1536-dimensional OpenAI
embedding distance; local fallback preserves availability. Redis wrappers cache
only hashed queries/vectors and knowledge-base results. The validated corpus has
100 references/rubrics/question prompts with explicit item type, role, and
seniority metadata; those fields survive the SQL round trip.

Local ranking treats category, role, seniority, rubric, and question words as
routing metadata. Issue-specific tag/title/body overlap controls relevance, and
finding explanations/suggestions provide safe derived query context.
PostgreSQL lexical queries use a bounded 64-term OR expression; requiring every
term caused broad review queries to return no rows.

## Decisions

- Embedding absence degrades to lexical retrieval.
- Cache/provider/database failure must not block review.
- Citation IDs remain stable across local and SQL paths.
- The comparison runner hashes queries in reports and never includes raw source
  or query text.

## Known gaps

- Local and PostgreSQL lexical comparison is measured and green. PostgreSQL
  vector-only and hybrid measurements require an OpenAI key and seeded
  embeddings; no semantic reranker is implemented.
