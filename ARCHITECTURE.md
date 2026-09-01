# Architecture

## Overview

Clutch is a read-only AI review and interview prep system built around one
well-scoped agent. The user submits code through Streamlit. Streamlit calls a
FastAPI backend. FastAPI validates the request, invokes a LangGraph agent, and
returns structured Pydantic outputs. The agent uses direct internal tools for
static review and clean-code retrieval, and later uses one MCP server for
external GitHub fetch operations.

The first runnable milestone is intentionally small:

```text
Streamlit pasted-code form
  -> FastAPI /review
  -> Pydantic request model
  -> static review service
  -> Pydantic CodeFinding[]
  -> Streamlit findings view
```

Tree-sitter parsing, retrieval, LangGraph orchestration, GitHub MCP, evals,
guardrails, tracing, Redis, and cloud deployment are added in that order as the
earlier slice becomes runnable.

## System Components

### Streamlit UI

Streamlit is the only v1 web client. It should stay focused on the review and
interview workflow rather than becoming a marketing site.

Initial screens:

- Review input: pasted code, language, role/seniority context, submit button.
- Findings output: severity, category, evidence, explanation, suggestion, and
  citations.
- Interview mode: generated questions, answer input, next-turn response.
- Progress view: recurring issues, improvement tasks, and session history.

### FastAPI Backend

FastAPI owns the service boundary. Streamlit should not call model providers,
retrieval code, databases, or MCP tools directly.

Initial endpoints:

- `POST /review`: accepts pasted code and returns `CodeFinding[]`.
- `POST /questions`: accepts review findings and returns
  `InterviewQuestion[]`.
- `POST /interview/turn`: accepts session state and a user answer, streams or
  returns the next interviewer turn.
- `GET /health`: local and deployment health check.

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

Initial retrieval can be vector-only over a small seeded corpus. Phase 2
upgrades retrieval to hybrid search using pgvector plus PostgreSQL full-text
search, with reranking if evals justify it.

Every retrieved item should carry:

- Stable source id.
- Title.
- Body text.
- Tags such as role, language, category, seniority, and source type.
- Citation metadata that can be surfaced in findings and reports.

### MCP Boundary for GitHub

MCP is used for one deliberate external boundary: GitHub fetch operations.

The MCP server exposes:

- `fetch_repo`
- `fetch_pr_diff`
- `list_repo_files`

It must remain read-only in v1. The agent consumes this MCP server as a client.
Internal rubric/question retrieval remains a normal app tool because it is
tightly coupled to the product's own knowledge store.

### Data Stores

PostgreSQL stores durable app data:

- Review sessions.
- Interview sessions.
- Feedback reports.
- Progress snapshots.
- Knowledge-base items.
- Retrieval metadata.

pgvector stores embeddings inside PostgreSQL so the project does not need a
separate vector database for v1.

Redis is introduced later for:

- Embedding cache.
- Retrieval result cache.
- Short-lived session acceleration.
- Before/after latency measurements.

### Observability

Langfuse or Arize Phoenix should trace:

- Request id.
- User workflow.
- Prompt and context assembly metadata.
- Model name and configuration.
- Tool calls and tool latency.
- Retrieval inputs and selected documents.
- Token usage, cost, and latency.
- Structured output validation failures.

Raw uploaded code should not be stored in observability events. Log metadata,
hashes, line counts, language, and issue categories instead.

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

1. User submits code in Streamlit.
2. Streamlit sends `ReviewRequest` to FastAPI.
3. FastAPI validates size, language, and required fields.
4. Backend treats code as untrusted input and passes it as quoted source data,
   never as instructions.
5. Parser extracts line-aware chunks when parsing exists; before that, the
   static review path can use the raw pasted snippet.
6. Retrieval returns clean-code principles relevant to the code and role
   context.
7. LangGraph assembles bounded context and requests structured findings.
8. Pydantic validates `CodeFinding[]`; invalid output is rejected or retried.
9. FastAPI returns structured findings to Streamlit.

### GitHub Review

1. User submits a repository or PR link.
2. FastAPI requests files or diffs through the GitHub MCP server.
3. The MCP server fetches only read-only data.
4. The same parsing, retrieval, and review flow runs over selected chunks.

### Interview Turn

1. User starts from findings or generated questions.
2. FastAPI loads interview session state.
3. LangGraph chooses the next question or follow-up.
4. The response is returned normally first, then via SSE once streaming is
   introduced.
5. Session state updates with question, answer, assessment, and next step.

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

CI should eventually block deployment when core eval scores regress beyond an
agreed threshold.

## Deployment Architecture

Local development runs all services locally or through Docker Compose.

Cloud deployment uses:

- Streamlit container for the UI.
- FastAPI container for the backend.
- Agent code packaged with the backend unless scaling pressure requires a
  separate worker.
- AWS ECS/Fargate for containers.
- AWS RDS PostgreSQL with pgvector.
- AWS ElastiCache Redis.
- AWS Secrets Manager or SSM Parameter Store for secrets.
- S3 for non-sensitive artifacts if needed.
- GitHub Actions for CI/CD.

Detailed deployment choices live in `CLOUD.md`.

## Architecture Critique

### Overengineering Risks

- PostgreSQL, pgvector, Redis, LangGraph, MCP, tracing, and evals are a lot for
  an early repo. The mitigation is sequencing: the first runnable version uses
  only Streamlit, FastAPI, Pydantic, and a deterministic review stub or minimal
  model path.
- Hybrid retrieval should not be built until vector-only retrieval has a
  baseline that can be improved.
- Redis should wait until there is a measured repeated-call latency problem.
- Model comparison should wait until the eval set is stable enough to make the
  comparison meaningful.

### Missing Guardrail Risks

- Prompt injection must be treated as a product requirement, not a late test.
- Observability must avoid storing raw uploaded code.
- GitHub MCP tools must remain read-only; mutating operations should not be
  implemented in v1.

### Unclear Boundaries

- Streamlit is only a client; all business logic belongs behind FastAPI.
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
