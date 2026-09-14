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
- One six-node LangGraph graph with strict OpenAI structured output plus
  honestly labeled static/retrieval/template fallback output.
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

- Full local quality/security gates are green: Ruff, mypy, 118
  tests, deterministic evals, secret scanning, and dependency audit.
- Dataset `2026-09-10.v6` passes all deterministic thresholds across 15 review
  cases, including three multi-file repositories.
- Neon production is at Alembic `20260909_0003` with 120 active sourced rows,
  120 valid embeddings, and passing direct/pooled verification.
- The production retrieval comparison measured all four strategies. Local
  lexical alone passes every fixed gate and is the default; Neon hybrid remains
  available but below gate.
- The capped `gpt-5.4-mini` baseline passed at $0.028781 total with zero schema
  failures and 0.833 interview score-within-one agreement.
- Fresh 2026-09-09 Compose smoke: three images rebuilt, pgvector migration
  succeeded, five services became healthy, and review → interview → feedback →
  progress worked through the real HTTP/UI boundaries.
- Repeated synthetic review produced a Redis hit and dropped application
  latency from about 111 ms to 8.6 ms (single smoke, not a benchmark).
- Remote MCP HTTP client listed 10 files from public `pypa/sampleproject`.
- Terraform 1.16.x with AWS provider 6.63.0 validates without warnings.
- Three product screenshots were captured from the real local stack and added
  to the README with a concrete example, failure analysis, and resume bullets.
- On 2026-09-09, the non-Docker app runtime was verified from `.venv` while
  Docker Postgres/Redis/LocalStack stayed up: FastAPI, Streamlit, and GitHub MCP
  health checks passed, pasted-code and GitHub reviews returned `mode: model`,
  cache/spend endpoints responded, and Langfuse `auth_check` passed.
- On 2026-09-10, real browser checks covered model success, forced fallback,
  rule-based interview assessment, errors, empty state, keyboard focus, and a
  390px layout without horizontal overflow.

## Decisions

- Keep the one-agent, read-only architecture; no mutation or multi-agent layer.
- Prefer AI stages, but label deterministic findings, template questions,
  rule-based assessments, retrieved citations, and final aggregation literally.
- Never persist or trace raw code, finding evidence, private repo contents, or
  interview answers.
- Redis caches knowledge-base derived data only. Langfuse automatic IO capture
  is disabled and the client flushes on graceful shutdown.
- Docker runs as UID/GID 10001. Alembic is an explicit one-off step.
- Terraform task count defaults to zero and AWS apply is a user checkpoint.
- Keep the live-model harness isolated from CI and capped at $0.50/run by
  default; missing credentials must return a typed unavailable report at $0.

## Frontend polish (2026-09-14)

Streamlit startup now uses a light base, local fonts, and a frontend-only
requirements file. The landing offers highlighted example evidence, a suggested
revision, and source links; native disclosures avoid server reruns. Navigation
and form busy states are clearer. Frontend tests and browser checks pass; this
revision is local and hosted speed has not been measured. Community Cloud's
pre-app shell/hibernation remains a hosting limit; see `docs/free-deployment.md`.

## Known gaps / next work

- Neon and local implementation are complete. The remaining owner steps are
  rotating deployment keys, deploying Render, deploying Streamlit Community
  Cloud, and running the hosted smoke/manual checklist.
- Baseline `2026-09-10.v6` remains bounded fixture evidence, not proof of general
  review or interview quality. Neon hybrid ranking should improve before it can
  replace the measured lexical default.
- The fallback Langfuse trace passes audit. The model trace still lacks native
  cost in Japan Cloud API readback despite native model/version/usage fields;
  keep this limitation visible.
- Deployment API-key auth and shared per-call/daily OpenAI spend reservations
  are implemented. Streamlit now uses Stytch email magic links for the hosted
  user gate; rate limiting and key-rotation automation remain later hardening.
- AWS needs account, region, budget, ingress, teardown, and credential approval;
  no paid resource has been provisioned.
