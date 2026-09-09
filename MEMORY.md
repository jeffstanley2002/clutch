# Project Memory

## Current state

The accelerated 14-day plan is implemented through the local Docker and
unapplied Terraform scaffold, spanning the master plan's Phases 1–4. The full
local workflow is runnable: paste or link Python code, get structured/cited
findings and questions, complete interview turns, and view durable progress.

Implemented boundaries:

- Streamlit Review / Interview / Progress workflow, browser-verified at desktop
  and 390px.
- FastAPI review, GitHub review, interview, progress, cache metrics, and health
  endpoints.
- One six-node LangGraph graph with static fallback and strict OpenAI structured
  output when configured.
- Tree-sitter Python parsing, local retrieval, and PostgreSQL FTS + pgvector
  hybrid retrieval.
- Privacy-safe review/interview/progress persistence with Alembic.
- Exactly three read-only GitHub MCP tools over in-process or Streamable HTTP.
- Hashed Redis embedding/retrieval caching and privacy-reduced Langfuse spans.
- Deterministic eval/guardrail gates, secret scanning, dependency audit, CI
  image builds, and Terraform validation.
- Privacy-reduced provider retry/validation counters and a separate spend-capped
  live-model evaluation over six reviews plus all three injection fixtures.
- Five-service Compose stack and non-root images; AWS module is validated but
  has never been applied.

## Verified evidence

- Full local quality/security gates are green: Ruff, mypy over 63 files, 83
  tests, deterministic evals, secret scanning, and dependency audit.
- Dataset `2026-09-08.v5` passes all deterministic thresholds across 15 review
  cases, including three multi-file repositories.
- The reproducible retrieval comparison passes for local and PostgreSQL lexical
  modes. They match at Precision@3 0.786, Recall@3 0.559, and MRR 1.0;
  PostgreSQL lexical nDCG@3 is 0.914 in the recorded local run.
- Fresh 2026-09-09 Compose smoke: three images rebuilt, pgvector migration
  succeeded, five services became healthy, and review → interview → feedback →
  progress worked through the real HTTP/UI boundaries.
- Repeated synthetic review produced a Redis hit and dropped application
  latency from about 111 ms to 8.6 ms (single smoke, not a benchmark).
- Remote MCP HTTP client listed 10 files from public `pypa/sampleproject`.
- Terraform 1.16.x with AWS provider 6.63.0 validates without warnings.
- Three product screenshots were captured from the real local stack and added
  to the README with a concrete example, failure analysis, and resume bullets.

## Decisions

- Keep the one-agent, read-only architecture; no mutation or multi-agent layer.
- Default to useful in-memory/static behavior when optional services are absent.
- Never persist or trace raw code, finding evidence, private repo contents, or
  interview answers.
- Redis caches knowledge-base derived data only. Langfuse automatic IO capture
  is disabled and the client flushes on graceful shutdown.
- Docker runs as UID/GID 10001. Alembic is an explicit one-off step.
- Terraform task count defaults to zero and AWS apply is a user checkpoint.
- Keep the live-model harness isolated from CI and capped at $0.50/run by
  default; missing credentials must return a typed unavailable report at $0.

## Known gaps / next work

- Local implementation is complete for the 14-day plan. Deployment evidence
  still needs user-owned OpenAI/Langfuse credentials, a scoped private-GitHub
  token, and AWS choices/credentials.
- Baseline `2026-09-08.v5` covers 12 pasted and three multi-file GitHub review
  cases, complete interview assessment, deterministic feedback expectations,
  raw source/answer privacy, and the 100-item lower corpus target. Adaptive
  follow-ups remain deliberately deferred; credentialed vector-only/hybrid
  measurements are a deployment checkpoint.
- Deployment API-key auth and shared per-call/daily OpenAI spend reservations
  are implemented; user accounts, rate limiting, and key-rotation automation
  remain later hardening.
- AWS needs account, region, budget, ingress, teardown, and credential approval;
  no paid resource has been provisioned.
