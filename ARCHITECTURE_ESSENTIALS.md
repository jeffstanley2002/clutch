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

Every external/API/model boundary is Pydantic-validated. Model-backed stages are
preferred; unavailable or invalid model paths return explicitly labeled static,
template, or rule-based fallbacks. Neon provides durable PostgreSQL/pgvector,
Redis is optional, and Langfuse receives privacy-reduced traces.

## Current boundaries

- Streamlit renders Review, Interview, and Progress; it owns no business logic.
- FastAPI exposes `/review`, `/review/github`, `/interview/turn`, completed-session
  `/interview/*/feedback`, `/progress/*`, `/runtime/cache`, `/runtime/spend`, and
  `/health`.
- LangGraph owns the linear review workflow. There is no multi-agent layer.
- Tree-sitter owns Python structure and line ranges.
- Internal retrieval supports local lexical plus Neon full-text, pgvector, and
  hybrid strategies. The measured deployment default is local lexical because
  it alone passed the current fixed production retrieval gates.
- Redis caches only knowledge-base retrieval/embedding data behind hashed keys.
- MCP owns exactly three external GitHub reads; it exposes no mutation tool.
- PostgreSQL persists source hashes and derived review/interview/progress data,
  never raw code or finding evidence.
- Langfuse sees explicit redacted metadata spans, never raw source, prompts, or
  interview answers.

## Durable data

Alembic migrations through `20260909_0003` create review sessions/findings/questions,
interview sessions/turns, progress snapshots, knowledge-base items, retrieval
events, and agent runs. The knowledge table has PostgreSQL full-text indexing,
a 1536-dimensional pgvector column, and an HNSW index.

Raw review code becomes SHA-256 + line count before persistence. Raw interview
answers become SHA-256 + deterministic signal summary. Repository content stays
request-scoped.

## Runtime modes

- No `DATABASE_URL`/`CLUTCH_DB_*`: in-memory repositories and local retrieval.
- No OpenAI key: deterministic findings, template questions, and rule-based
  answer assessment are labeled with `model_not_configured`; durable sessions
  still work when the database is configured.
- OpenAI key configured: strict structured review/question/assessment calls;
  one validation retry, then the same labeled fallback. Every paid call reserves
  a conservative cost against per-call and UTC-daily ceilings before OpenAI.
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
  counter failure blocks the paid call before the provider request.

## Verified state

- Deterministic eval `2026-09-10.v6`: all committed gates pass across 15 review
  cases, three injection cases, and three complete interview cases; 118 tests,
  Ruff, and mypy are green.
- The capped `gpt-5.4-mini` baseline passed all mandatory gates at $0.028781
  total / $0.004797 per review, with zero schema failures.
- Neon production is at Alembic head with 120 active sourced items and 120
  1536-dimensional embeddings. Direct and pooled verification passed.
- Production retrieval measured all four strategies; local lexical won and is
  the default. The Neon hybrid/vector candidates remain below gate.
- Forced-fallback Langfuse trace audit passes. The model trace has native
  model/version/usage/latency, but Japan Cloud still reads native cost as empty,
  so that audit remains honestly failing.
- Local browser: complete Review → Interview → assessment/report → Progress
  flow, with committed screenshots from the rebuilt five-service stack.
- Docker: three non-root images build; pgvector Postgres migration and all five
  Compose health checks pass.
- Redis smoke: cold synthetic review ~111 ms, cached ~8.6 ms; one miss/write
  followed by one hit.
- Terraform: formatted and validated with Terraform 1.16.x / AWS provider
  6.63.0; never planned against an account or applied.

## Next sequence

1. Rotate deployment credentials, then deploy Render from `render.yaml` with the
   pooled Neon URL.
2. Deploy `frontend/app.py` to Streamlit Community Cloud and run the hosted
   smoke/manual privacy checklist.
3. Improve and remeasure Neon hybrid retrieval without weakening gates; switch
   only if a new baseline wins. Re-audit Langfuse native cost after provider
   readback changes.
