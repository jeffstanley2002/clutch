# Architecture Essentials

## Daily orientation

Clutch is a read-only code-review and interview-practice system. Streamlit is
one client; FastAPI is the service boundary; one LangGraph agent performs typed
review orchestration.

```text
Pasted Python -------------------------> FastAPI /review
GitHub repo/PR -> read-only MCP ------> FastAPI /review/github
                                             |
                  parse -> static signals -> retrieve -> synthesize
                    -> validate -> generate questions
                                             |
                 interview turns -> progress snapshots
```

Every external/API/model boundary is Pydantic-validated. Without optional
services the system runs in memory with deterministic review. With PostgreSQL,
Redis, OpenAI, and Langfuse configured it enables durable hybrid retrieval,
safe caching, model-backed synthesis, and privacy-reduced traces.

## Current boundaries

- Streamlit renders Review, Interview, and Progress; it owns no business logic.
- FastAPI exposes `/review`, `/review/github`, `/interview/turn`, completed-session
  `/interview/*/feedback`, `/progress/*`, `/runtime/cache`, `/runtime/spend`, and
  `/health`.
- LangGraph owns the linear review workflow. There is no multi-agent layer.
- Tree-sitter owns Python structure and line ranges.
- Internal retrieval uses PostgreSQL full-text plus optional pgvector similarity;
  an in-memory lexical fallback keeps zero-service mode runnable.
- Redis caches only knowledge-base retrieval/embedding data behind hashed keys.
- MCP owns exactly three external GitHub reads; it exposes no mutation tool.
- PostgreSQL persists source hashes and derived review/interview/progress data,
  never raw code or finding evidence.
- Langfuse sees explicit redacted metadata spans, never raw source, prompts, or
  interview answers.

## Durable data

Alembic migration `20260908_0001` creates review sessions/findings/questions,
interview sessions/turns, progress snapshots, knowledge-base items, retrieval
events, and agent runs. The knowledge table has PostgreSQL full-text indexing,
a 1536-dimensional pgvector column, and an HNSW index.

Raw review code becomes SHA-256 + line count before persistence. Raw interview
answers become SHA-256 + deterministic signal summary. Repository content stays
request-scoped.

## Runtime modes

- No `DATABASE_URL`/`CLUTCH_DB_*`: in-memory repositories and local retrieval.
- Database configured, no OpenAI key: PostgreSQL lexical retrieval and static
  review; durable sessions still work.
- OpenAI key configured: embeddings and strict structured synthesis; one retry,
  then `static_fallback`. Every paid call reserves a conservative cost against
  per-call and UTC-daily ceilings before it reaches OpenAI.
- `REDIS_URL` configured: cached embedding/retrieval results with fail-open
  timeouts and aggregate metrics.
- Langfuse explicitly enabled with both keys: redacted node/tool/retriever/
  generation spans, flushed at graceful shutdown.
- `GITHUB_MCP_URL` empty: in-process MCP transport; set it to `/mcp` for the
  deployed Streamable HTTP boundary.

## Guardrails

- Treat code, comments, strings, README text, diffs, and patches as untrusted.
- Bound request, tree, file, byte, prompt, retry, and output sizes.
- Reject non-GitHub URLs, unsafe refs/paths, redirects, unsupported extensions,
  binary/non-UTF-8 content, unknown citations, and impossible line ranges.
- Never persist or trace raw uploaded code.
- Never mutate repositories in v1; later mutation needs explicit per-action
  human approval.
- Optional local API-key auth becomes mandatory in Terraform whenever ECS task
  count is nonzero; only `/health` remains unauthenticated.
- Redis makes the daily spend reservation atomic across backend processes;
  counter failure blocks the paid call and preserves static fallback.

## Verified state

- Deterministic eval `2026-09-07.v1`: all committed gates pass.
- Local browser: complete Review → Interview → final report → Progress flow;
  the report was rechecked at 390px with no horizontal overflow.
- Docker: three non-root images build; pgvector Postgres migration and all five
  Compose health checks pass.
- Redis smoke: cold synthetic review ~111 ms, cached ~8.6 ms; one miss/write
  followed by one hit.
- Terraform: formatted and validated with Terraform 1.16.1 / AWS provider
  6.63.0; never planned against an account or applied.

## Next sequence

1. Compare deterministic lexical, credentialed vector-only, and hybrid
   retrieval against the same `2026-09-08.v5` judgments; the 100-item lower
   corpus target and multi-file cases are complete.
2. Add adaptive interview follow-ups only if the expanded deterministic and
   controlled live-model evals justify another model call.
3. With user credentials, capture controlled OpenAI and Langfuse baselines and
   verify a read-only private GitHub repository.
4. Only after account/region/budget/teardown approval, review an AWS saved plan,
   publish immutable images, run migrations, and deploy staging.
