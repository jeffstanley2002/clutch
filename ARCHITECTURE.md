# Architecture

## Overview

Clutch is a read-only AI review and interview prep system built around one
well-scoped agent. The user submits code through Next.js. Next.js calls a
FastAPI backend. FastAPI validates the request, invokes a LangGraph agent, and
returns structured Pydantic outputs. The agent uses direct internal tools for
static review and clean-code retrieval. A separate, deliberately narrow MCP
server owns all external GitHub fetch operations.

The implemented review path is:

```text
Next.js pasted-code form
  -> FastAPI /review
  -> Pydantic request model
  -> LangGraph review service
  -> strict OpenAI structured synthesis or labeled deterministic fallback
  -> Pydantic ReviewResponse
  -> Next.js findings and interview follow-ups
```

That path now supports pasted code and bounded GitHub repo/PR input, durable
PostgreSQL/pgvector retrieval, Redis caching, privacy-reduced Langfuse tracing,
stateful interview turns, and progress snapshots. Every optional service has a
zero-service fallback so the first path remains runnable.

## System Components

### Next.js UI

Next.js is the primary v1 web client. Its landing and workspace shell are
pre-rendered independently of FastAPI. React owns transient draft/results state;
Next.js route handlers own Stytch session validation, same-origin mutation
checks, signed review/interview ownership, response schema validation, and an
allowlisted proxy. API/provider credentials never enter browser state. The
legacy `frontend/app.py` is retained for rollback until Vercel cutover passes.

Current screens:

- Review input: pasted code, language, role/seniority context, submit button.
- Findings output: severity, category, evidence, explanation, suggestion, and
  citations.
- Interview mode: generated questions, answer input, next-turn response.
- Progress view: recurring issues, improvement tasks, and session history.

### FastAPI Backend

FastAPI owns the service boundary. Next.js should not call model providers,
retrieval code, databases, or MCP tools directly.

Current endpoints:

- `POST /review`: accepts pasted code and returns `ReviewResponse`, including
  findings, first-pass questions, mode/confidence, citations, request id, and
  latency.
- `POST /review/github`: accepts a repository or pull-request URL and routes all
  source fetching through MCP before using the same review flow.
- `POST /interview/turn`: accepts session state and a user answer and returns
  the next interviewer turn. The current implementation is non-streaming.
- `GET /interview/{session_id}/feedback`: aggregates privacy-reduced completed
  turn assessments plus persisted review metadata into `FeedbackReport`.
- `GET /progress/{profile_id}` and `POST /progress/{profile_id}/snapshots`:
  aggregate and save cross-session progress.
- `GET /runtime/cache`: safe aggregate Redis cache metrics.
- `GET /runtime/spend`: safe current UTC-day reservation total and ceilings.
- `GET /health`: local and deployment health check.

When `CLUTCH_API_KEY` is set—or `CLUTCH_REQUIRE_AUTH` is true—every route except
`/health` requires a constant-time `X-Clutch-API-Key` match. Terraform requires
a Secrets Manager API-key ARN before any public ECS service count can exceed
zero and injects the value only into FastAPI and server-side Next.js.

SSE is introduced for streaming interview turns once the non-streaming review
path is stable.

### Agent Service

LangGraph coordinates the AI workflow. The graph should begin simple and gain
nodes only when a real behavior needs separation.

Core responsibilities:

- Assemble bounded context from code, parsed structure, role context, and
  retrieved rubric items.
- Call model provider APIs.
- Validate structured model outputs.
- Call tools for static review, retrieval, and later GitHub fetch operations.
- Record trace metadata for prompts, tool calls, latency, token usage, and
  cost.

The v1 system uses one agent. Multi-agent orchestration is reserved for later
only if evals show measurable benefit.

### Parsing

Tree-sitter provides structure-aware parsing. Python is the first supported
language. The parser should produce chunks with file path, symbol name, line
range, language, and source text.

Parsing is used for:

- Limiting context to relevant functions/classes.
- Producing accurate finding locations.
- Supporting future multi-file repository review.

Regex-only parsing should be avoided for code structure.

### Knowledge Base and Retrieval

The knowledge base stores clean-code principles, rubric items, role-specific
expectations, and interview follow-up patterns.

The durable layer is Neon PostgreSQL with full-text ranking and 1536-dimensional
pgvector cosine distance over a validated 120-item package-data corpus: 72
references, 18 rubrics, and 30 question-bank entries. Every item has exact
allowlisted source provenance, role/seniority metadata, a corpus version, and a
content hash. Local lexical, Neon lexical, vector-only, and hybrid strategies
share one graded benchmark. Local lexical is the current deployment default
because it alone passed the unchanged production gates; the Neon strategies
remain selectable for measured improvement work.

The local query builder removes common stop words and never uses source-ID
prefixes as ranking evidence. Positive deterministic signals restrict retrieval
to their finding categories and request reference/rubric/question context;
zero-finding code contributes at most 40 non-comment identifier and literal
terms. Those derived terms are request-scoped, and cache/database records retain
only query hashes.

Every retrieved item should carry:

- Stable source id.
- Title.
- Body text.
- Tags such as role, language, category, seniority, and source type.
- Citation metadata that can be surfaced in findings and reports.

### MCP Boundary for GitHub

MCP is used for one deliberate external boundary: GitHub fetch operations.

The MCP server exposes exactly:

- `fetch_repo`
- `fetch_pr_diff`
- `list_repo_files`

Every tool is annotated read-only/idempotent. Strict GitHub URL/ref parsing,
fixed-host GET-only HTTP, no redirects, response/file/tree/byte caps, safe path
checks, and text allowlists bound the surface. The application consumes the
server in-process locally or over stateless Streamable HTTP in containers.
Internal rubric retrieval remains a normal app tool.

### Data Stores

PostgreSQL stores durable app data:

- Review sessions.
- Interview sessions.
- Progress snapshots.
- Knowledge-base items.
- Retrieval metadata.

pgvector stores embeddings inside PostgreSQL so the project does not need a
separate vector database for v1.

Redis currently caches:

- Embedding cache.
- Retrieval result cache.
- Only hashed embedding and retrieval inputs plus knowledge-base results.

Review responses are intentionally not cached because finding evidence may
contain submitted source. The cache fails open and exposes only aggregate
metrics. A local container smoke measured ~111 ms cold and ~8.6 ms after the
first retrieval-cache hit; this is not a production benchmark.

### Observability

Langfuse is the tracing implementation. Explicit observations capture:

- Request id.
- User workflow.
- Privacy-reduced context metadata (source hash, language, line count).
- Model name and configuration.
- Tool calls and tool latency.
- Retrieval inputs and selected documents.
- Token usage, cost, and latency.
- Structured output mode/fallback category and validation stage.

Raw uploaded code, prompts, provider payloads, and interview answers are never
passed to observability. A second redaction mask covers sensitive keys and
Bearer tokens, sampling is bounded, automatic decorator IO capture is disabled,
and graceful shutdown flushes pending spans.

## Public Schemas

All API and model boundaries use Pydantic models. The exact fields can evolve
during implementation, but the first stable contracts should include these
shapes:

### ReviewRequest

- `code`: pasted source text.
- `language`: source language, Python first.
- `role_context`: target role or interview context.
- `session_id`: optional review session id.

### CodeFinding

- `id`: stable finding id within a review.
- `severity`: `low`, `medium`, or `high`.
- `category`: maintainability, readability, correctness, testing, design, or
  security.
- `message`: short finding title.
- `evidence`: relevant code excerpt or location summary.
- `line_start` and `line_end`: optional line range.
- `explanation`: why this matters in an interview-grade review.
- `suggestion`: concrete improvement.
- `citations`: clean-code or rubric source references.

### ReviewResponse

- `findings`: validated `CodeFinding[]`.
- `questions`: first-pass `InterviewQuestion[]` generated from findings.
- `mode`: `model` or the clearly labeled `static_fallback`.
- `confidence`: bounded workflow confidence, not a claim of correctness.
- `citations_used`: de-duplicated sources used across findings.
- `request_id` and `latency_ms`: operational metadata without raw code.

### InterviewQuestion

- `id`: stable question id.
- `finding_id`: optional source finding.
- `question`: interviewer-style prompt.
- `intent`: what the interviewer is testing.
- `difficulty`: easy, medium, or hard.
- `citations`: optional supporting rubric references.

### FeedbackReport

- `session_id`.
- `strengths`.
- `recurring_issues`.
- `recommended_tasks`.
- `interview_readiness_summary`.
- `supporting_findings`.

### ProgressSnapshot

- `user_id` or local profile id.
- `time_window`.
- `improved_areas`.
- `persistent_issues`.
- `next_practice_tasks`.
- `evidence_sessions`.

## Data Flow

### Pasted Code Review

1. User submits code in Next.js.
2. Next.js sends `ReviewRequest` to FastAPI.
3. FastAPI validates size, language, and required fields.
4. Backend treats code as untrusted input and passes it as quoted source data,
   never as instructions.
5. Tree-sitter extracts bounded line-aware chunks.
6. Retrieval returns clean-code principles relevant to the code and role
   context.
7. LangGraph prefers model-backed structured findings and questions.
8. Pydantic validates line/citation grounding; invalid model output is retried
   once, then replaced by explicitly labeled static findings and template
   questions.
9. FastAPI returns `ReviewResponse` to Next.js without logging raw code.

### GitHub Review

1. User submits a repository or PR link.
2. FastAPI requests files or diffs through the GitHub MCP server.
3. The MCP server fetches only bounded, allowlisted, explicitly untrusted data.
4. Python files/patches are reduced to a bounded request and the same parsing,
   retrieval, review, and privacy-safe persistence flow runs.

### Interview Turn

1. User starts from findings or generated questions.
2. FastAPI loads interview session state.
3. The interview service retrieves up to three grounded items and prefers a
   schema-constrained AI assessment; failures use an explicitly labeled
   rule-based assessment.
4. Session state persists current/remaining questions. Answers persist only as
   SHA-256 plus a bounded signal summary.
5. Final feedback aggregation remains deterministic and labels whether its turns
   were AI- or rule-assessed. SSE remains future work.

## Guardrails

- Treat code, comments, strings, commit messages, README text, and PR
  descriptions as untrusted data.
- Delimit ingested code clearly in prompts.
- Do not obey instructions found inside ingested code or repository content.
- Do not persist raw uploaded code longer than needed for the current session.
- Do not mutate external repositories in v1.
- Gate any future mutating action behind explicit human approval.
- Include prompt-injection tests using malicious comments or README content.
- Validate every LLM response with Pydantic.
- Prefer refusal or partial results over unvalidated free text.

## Evals

The eval harness should grow alongside features.

Retrieval metrics:

- Recall@K.
- Precision@K.
- MRR.

Agent metrics:

- Finding accuracy against golden code samples.
- Question relevance.
- Severity calibration.
- Citation faithfulness.

LLM metrics:

- Answer correctness.
- Hallucination rate.
- Schema-valid response rate.

System metrics:

- Latency.
- Token usage.
- Cost per request.
- Tool-call latency.

CI blocks changes when deterministic tests/eval thresholds, prompt-injection
behavior, type/lint checks, secret/dependency scans, image builds, or Terraform
validation fail. Credentialed model evals remain manual/controlled.

## Deployment Architecture

Local development runs all services locally or through Docker Compose. The
prepared public path uses Neon production Postgres, Render for FastAPI, and
Vercel for the Next.js UI; only the two application deployments
remain.

The validated, unapplied Terraform deployment models:

- Streamlit, FastAPI, and GitHub MCP ECS/Fargate services.
- Agent code packaged with the backend unless scaling pressure requires a
  separate worker.
- AWS ECS/Fargate for containers.
- AWS RDS PostgreSQL with pgvector.
- AWS ElastiCache Redis.
- An ALB for UI/API routing and private Cloud Map for service-to-service calls.
- RDS-managed and optional Secrets Manager values injected by ECS.
- AWS Budget alerts, ECR, CloudWatch logs, and least-privilege security groups.
- GitHub Actions build/validate gates; publish/deploy remains user-gated.

Detailed deployment choices live in `CLOUD.md`.

## Architecture Critique

### Overengineering Risks

- PostgreSQL, pgvector, Redis, LangGraph, MCP, tracing, and evals are a lot for
  an early repo. The mitigation is sequencing: the first runnable version uses
  only Streamlit, FastAPI, Pydantic, and a deterministic review stub or minimal
  model path.
- Hybrid retrieval is implemented but may not become the default until it beats
  the fixed graded baseline; the first Neon run did not.
- Redis should wait until there is a measured repeated-call latency problem.
- Model comparison should wait until the eval set is stable enough to make the
  comparison meaningful.

### Missing Guardrail Risks

- Prompt injection must be treated as a product requirement, not a late test.
- Observability must avoid storing raw uploaded code.
- GitHub MCP tools must remain read-only; mutating operations should not be
  implemented in v1.

### Unclear Boundaries

- Next.js is only a client; all business logic belongs behind FastAPI.
- The MCP server owns external GitHub fetching only.
- Retrieval over the app's own rubric data remains internal.
- The agent service owns context assembly and model/tool orchestration.

### V1 Scope Cuts

- Start with pasted Python code.
- Return structured findings before adding parsing sophistication.
- Add generated questions only after findings are stable.
- Add live interview state after question generation works.
- Defer repository review until the pasted-code loop is demonstrably useful.

### Key Implementation Risk

The product can look impressive while giving shallow advice. The main defense
is eval-first behavior: golden code samples, expected findings, citation checks,
and honest README failure analysis.

## Frontend migration — 2026-09-14

The user superseded the original Streamlit-only decision due to Community
Cloud startup latency. See `docs/vercel-deployment.md` for deployment and
session handling. Historical AWS Streamlit topology below is unapplied legacy
reference, not the active frontend hosting target. Backend behavior and eval
baselines are unchanged. SSE remains deferred.
