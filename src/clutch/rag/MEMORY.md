# RAG Memory

## Current state

Retrieval supports local lexical search and durable Neon PostgreSQL search.
PostgreSQL combines full-text rank with optional 1536-dimensional OpenAI
embedding distance; local fallback preserves availability. Redis wrappers cache
only hashed queries/vectors and knowledge-base results. The validated corpus has
120 references/rubrics/question prompts with exact provenance; those fields
survive the SQL round trip.

Local ranking treats category, role, seniority, rubric, and question words as
routing metadata. Issue-specific tag/title/body overlap controls relevance, and
finding explanations/suggestions provide safe derived query context.
PostgreSQL lexical queries use a bounded 64-term OR expression; requiring every
term caused broad review queries to return no rows.

## Decisions

- `CLUTCH_RETRIEVAL_STRATEGY` selects local lexical, Neon lexical, vector, or
  hybrid. Missing database/model dependencies degrade to local retrieval.
- Cache/provider/database failure must not block review.
- Citation IDs remain stable across local and SQL paths.
- The comparison runner hashes queries in reports and never includes raw source
  or query text.

## Known gaps

- The 2026-09-10 Neon baseline measured all four strategies. Local lexical alone
  passed every fixed gate (P@3 0.800, R@3 0.563, MRR 1.000, nDCG@3 0.970) and is
  the deployment default. Neon hybrid measured nDCG@3 0.872 and remains a
  non-default candidate until ranking improves without a gate change.
