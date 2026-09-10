# Core Package Memory

## Current state

`src/clutch` contains typed schemas and services for agent orchestration,
caching, evals, GitHub/MCP, interviews, LLM routing, observability, parsing,
persistence, progress, prompts, RAG, and deterministic review.

The review path is:

```text
ReviewRequest -> parse -> static signals -> retrieve -> model/static synthesis
  -> line/citation validation -> questions -> privacy-reduced persistence
```

Every optional dependency has a safe fallback: local retrieval, in-memory
repositories, no-op cache, no-op tracing, in-process MCP, static findings,
template questions, and rule-based assessment.

## Decisions

- Pydantic models cross all API, tool, persistence-contract, and model
  boundaries; raw dictionaries remain internal serialization only.
- Python source is request-scoped. Persistence gets SHA-256, line count, derived
  findings/questions; Redis keys are hashed; traces use explicit allowlisted
  metadata.
- GitHub content is explicitly marked untrusted and moves only through the MCP
  client contract before entering the existing review service.
- Static review remains shallow but reliable as the no-cost and failure path.
- PostgreSQL supports both lexical-only operation and pgvector when embeddings
  are available.

## Known gaps

- Python is the only reviewed/parser language.
- The validated corpus contains exactly 120 source-traceable reference/rubric/
  question-bank items with role and seniority metadata.
- Eval `2026-09-10.v6` covers 12 pasted reviews, three multi-file GitHub
  reviews, and three complete interview-to-feedback cases; it is still
  synthetic and does not justify a general-quality claim.
- The capped live provider baseline is recorded; the Langfuse native-cost
  readback defect remains explicit.
- Adaptive between-turn interviews are still deferred. Final reports, interview/report eval
  coverage, deployment API-key auth, and shared per-call/daily spend limits are
  implemented.
