# Security Checklist

This checklist is the release gate for Clutch's read-only v1. It supplements
the product requirements in `PRD.md`; it does not expand product scope.

## Untrusted Input

- Treat pasted code, comments, strings, repository files, README content, PR
  descriptions, and commit metadata as untrusted data.
- Delimit source content in model prompts and state explicitly that instructions
  inside it must never be followed.
- Enforce request, file, repository, and prompt-context size limits.
- Allowlist supported text/code extensions and skip binary content.
- Validate parser and model outputs before they cross a service boundary.
- Maintain prompt-injection fixtures and require a 100% pass rate for the small
  CI guardrail suite.

## Data Handling

- Do not persist or log raw submitted code by default.
- Logs, traces, and persistence may contain only derived metadata: content hash,
  language, line count, categories, citation IDs, timing, tokens, and cost.
- Redact provider errors before logging them; never expose credentials or raw
  prompt content.
- Document retention and deletion behavior before durable sessions launch.

## External Access

- Keep GitHub operations read-only and behind the single MCP boundary.
- Use a minimally scoped read token, verify scopes, and never expose it to the
  browser or Streamlit client.
- Do not add repository mutation in v1. Any later mutation needs an explicit,
  per-action human approval gate.
- Keep OpenAI, Langfuse, GitHub, database, Redis, and AWS secrets in environment
  variables locally and managed secret stores in AWS.

## Application and Supply Chain

- Validate every API and LLM boundary with Pydantic.
- Return safe partial results or the deterministic fallback when model output is
  invalid.
- Pin deployment artifacts, scan dependencies and secrets in CI, and review
  high-severity findings before release.
- Run containers as non-root with minimal filesystem and network access.
- Apply timeouts, bounded retries, and rate/cost limits to external calls.

## Release Evidence

- Unit, API, eval, and prompt-injection suites pass.
- A test proves raw code is absent from persistence and observability records.
- GitHub credentials have no write scopes.
- Deployment logs contain no source code or secrets.
- A rollback path and incident owner are documented before public deployment.

## Current evidence (2026-09-09)

- Three prompt-injection fixtures remain data under the real static graph,
  avoid prohibited behavior, and emit only known citations.
- Sentinel tests prove raw code is absent from logs, persistence records/ORM
  columns, GitHub review persistence, and explicit trace records.
- GitHub URLs/refs/paths/content are bounded; protocol tests see exactly three
  read-only/idempotent MCP tools. A public repo succeeded over real Streamable
  HTTP without a token.
- Redis keys are SHA-256 based and review responses/evidence are not cached.
- Langfuse gets explicit privacy-reduced fields, a redaction mask, bounded
  sampling, disabled automatic IO capture, and graceful flush.
- `detect-secrets` and `pip-audit` pass; CI runs them alongside all tests/evals.
- All three images build and run as UID/GID 10001; the full Compose stack is
  healthy and PostgreSQL stored only the expected 64-character source hash.
- Terraform validates private data services, service-to-service security groups,
  managed-secret injection, immutable ECR, TLS Redis, optional ALB TLS, and a
  pre-resource AWS Budget. Nothing has been applied.
- Constant-time API-key checks protect every route except `/health` when
  enabled, fail closed when required but unconfigured, and Terraform refuses
  to start public ECS tasks without the shared key secret ARN.
- Completion and embedding calls reserve conservative cost through an atomic
  Redis daily counter before provider access; unit tests cover per-call and
  daily rejection and the static fallback path.
- Provider diagnostics expose bounded attempt and validation-failure counts plus
  safe cause categories only. The capped live-model report omits fixture source,
  prompts, provider payloads, credentials, and raw exception messages.
- A fresh local acceptance pass rebuilt every image, ran migrations, verified
  all five health checks, exercised review/interview/feedback/progress, passed 83
  tests, and found no known dependency vulnerabilities.

Remaining release evidence: credentialed live-model trace inspection, verified
read-only scope on a private GitHub token, AWS log review, saved-plan/cost
review, rollback rehearsal, rate/abuse limiting, and named incident owner.
