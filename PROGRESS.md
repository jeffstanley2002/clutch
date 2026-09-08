# Progress Log

## 2026-09-01 (Day 0)

Phase: Initialization

Did:

- Created the product and architecture documentation required before code.
- Captured the architecture critique in `ARCHITECTURE.md`.
- Added `ARCHITECTURE_ESSENTIALS.md` for quick daily orientation.
- Added `CLOUD.md` for deployment and infrastructure planning.
- Added root `MEMORY.md` for current project state.

Learned / decided:

- The repo currently begins from documentation only.
- The first runnable build should be pasted Python code review through
  Streamlit and FastAPI.
- GitHub ingestion, live interviews, Redis, tracing, and deployment should wait
  until the pasted-code review loop works.

Open issues:

- No Python project scaffold exists yet.
- The repo is not initialized as a git repository.
- Tracing provider is undecided: Langfuse or Arize Phoenix.
- The exact initial OpenAI model is undecided.

Next up:

- Initialize the Python project and repo structure.
- Scaffold Streamlit, FastAPI, shared Pydantic schemas, and the first
  `/review` route.
- Add the smallest tests proving the route returns structured findings.

## 2026-09-01 (Day 1)

Phase: 1

Did:

- Initialized the folder as a git repository.
- Added Python project metadata, `.gitignore`, `.env.example`, and a starter
  `README.md`.
- Added shared Pydantic schemas for review requests/findings plus future
  interview, feedback, and progress contracts.
- Added a deterministic static reviewer for the first local `/review` path.
- Added FastAPI `GET /health` and `POST /review`.
- Added a Streamlit pasted-code UI that calls the FastAPI review endpoint.
- Added backend tests for health, structured findings, and blank-code
  validation.
- Created folder memory files for backend, frontend, and the core package.
- Created `.venv`, installed Day 1 dependencies, and started local FastAPI and
  Streamlit servers.

Learned / decided:

- Keep Day 1 review deterministic so the API and UI contract is testable before
  parser, retrieval, LangGraph, and LLM behavior are added.
- Return `list[CodeFinding]` directly from `/review` to match the architecture's
  first endpoint contract.

Open issues:

- Static review catches only simple patterns: TODO/FIXME, debug prints, bare
  excepts, mutable defaults, and overly long snippets.
- No tree-sitter parsing, clean-code retrieval, LangGraph orchestration, or
  model call exists yet.
- The first pytest run in `.venv` passes with one upstream Starlette/FastAPI
  deprecation warning about `TestClient`.

Next up:

- Add the Python parsing layer with line-aware chunks.
- Route `/review` through parsed snippet metadata while preserving the same
  `CodeFinding[]` API shape.

## 2026-09-02 (Day 2)

Phase: 1

Did:

- Added Pydantic `CodeChunk` and `ParsedCode` models for parser output.
- Added a tree-sitter Python parser that extracts line-aware class/function
  chunks and falls back to a module chunk for snippets without definitions.
- Moved tree-sitter dependencies into core runtime dependencies because
  `/review` now parses every Python request.
- Routed FastAPI `POST /review` through parser metadata before deterministic
  static review.
- Added parser unit tests and an API test proving large-function findings use
  parsed line metadata.

Learned / decided:

- Keep parser output internal for now so the public API remains
  `list[CodeFinding]`.
- Parser metadata is immediately useful for line-aware findings even before
  retrieval or LangGraph exists.

Open issues:

- Static review is still shallow and deterministic.
- Syntax errors are detected by parsing but not surfaced as a dedicated
  finding yet.
- No clean-code retrieval, LangGraph orchestration, or model-backed structured
  review exists yet.
- Pytest still shows the upstream Starlette/FastAPI `TestClient` deprecation
  warning.

Next up:

- Add the first seeded clean-code knowledge base and retrieval interface.
- Use retrieved seed principles as real citations for deterministic findings
  before introducing LangGraph or model calls.

## 2026-09-07 (Day 3)

Phase: 1

Did:

- Added `src/clutch/knowledge_base` with Pydantic `CleanCodePrinciple` seed
  records and deterministic lexical retrieval.
- Seeded the first clean-code corpus: incomplete work, observability, narrow
  error handling, mutable Python defaults, small reviewable units, and
  behavioral test boundaries.
- Updated the deterministic static reviewer so findings retrieve their
  citations from the seed knowledge base instead of using module-level
  placeholder citations.
- Added retrieval unit tests and strengthened API tests to assert specific
  citation source IDs.

Learned / decided:

- Keep Day 3 retrieval local and lexical so the pasted-code review loop stays
  runnable without Postgres, embeddings, or model calls.
- Treat the retrieval function as the stable interface that vector or hybrid
  retrieval can replace internally later.

Open issues:

- Retrieval is still tiny and lexical; no vector-only retrieval, pgvector,
  hybrid search, or reranking yet.
- Static review is still deterministic and shallow.
- No LangGraph orchestration or model-backed structured review exists yet.
- Pytest still shows the upstream Starlette/FastAPI `TestClient` deprecation
  warning.

Next up:

- Add the first LangGraph review orchestration layer with tools for
  `static_review` and `retrieve_clean_code_principles`, while preserving the
  same `/review -> CodeFinding[]` API shape.

## 2026-09-07 (Day 4)

Phase: 1 (14-day sprint Days 1–4)

Did:

- Added the six-node LangGraph review spine and an async `ReviewService`
  boundary so FastAPI only handles HTTP validation/delegation.
- Upgraded `/review` to `ReviewResponse`: findings, role-aware questions, mode,
  confidence, de-duplicated citations, request id, and latency.
- Preserved a fully local `static_fallback` path and added graph/API tests.
- Added an OpenAI provider using current Responses structured output, bounded
  versioned prompts, `store=False`, one validation retry, invented-citation and
  impossible-line rejection, and automatic fallback.
- Added provider/prompt tests, including untrusted prompt-injection text and
  source-size bounding.
- Added `SECURITY_CHECKLIST.md`, `COST_CONTROL.md`, and
  `EVALUATION_AND_GOVERNANCE.md` from the sprint plan.
- Established `DESIGN.md`, a Streamlit theme, and clearer empty/loading/error
  states; browser-verified the full review flow at desktop and 390px width.
- Chose Langfuse and `gpt-5.4-mini` as configurable first implementation
  defaults and reconciled the architecture/product docs.

Learned / decided:

- Keep LangGraph nodes explicit even while synthesis is deterministic; this
  gives model, validation, eval, and tracing work stable seams.
- Reject an entire ungrounded model response and retry once instead of quietly
  mixing untrusted model citations into valid static output.
- The evidence-first annotated-review-notebook direction fits the product and
  avoids generic AI-dashboard styling.

Open issues:

- The real OpenAI path is implemented but cannot be verified without
  `OPENAI_API_KEY` in local `.env`.
- Retrieval is still lexical over six seed principles; no eval baseline exists.
- Interview turns, persistence, GitHub MCP, tracing, Redis, CI, and deployment
  remain later sprint work.

Next up:

- Add `OPENAI_API_KEY` to `.env`, restart FastAPI, and capture the first live
  structured review result without logging raw source.
- Then build the eight-sample golden eval and prompt-injection gate.

## 2026-09-07 (Day 5)

Phase: 3 guardrail/eval slice (pulled forward by the 14-day sprint)

Did:

- Added eight typed golden review fixtures and three prompt-injection fixtures
  covering every issue class named in the sprint plan.
- Extended deterministic review and the seed knowledge base for unsafe SQL,
  duplicated logic, and explicit missing-test evidence.
- Made the review graph injectable and forced the eval runner through the real
  graph with a zero-cost static `ModelRouter`.
- Added a CLI eval harness for finding, retrieval, citation, question,
  hallucinated-line, injection, latency, and cost metrics.
- Added guardrail tests that prove adversarial source stays data and that a
  unique raw-code sentinel never appears in application logs.
- Removed eager package imports that caused a review/agent circular import.
- Finished green with 16 tests, Ruff, mypy across 21 source files, the compact
  eval gate, bytecode compilation, and `git diff --check`.

Learned / decided:

- The `2026-09-07.v1` deterministic baseline passes all gates: finding
  precision/recall, Retrieval Recall@3/MRR, citation faithfulness, question
  relevance, and injection pass rate are 1.0; hallucinated-line rate is 0.0.
- Retrieval Precision@3 is 0.333 by construction because each fixture labels
  one relevant citation while the retriever returns three candidates.
- A static run must report model structured-output validity as unmeasured, not
  as a misleading zero failure rate.

Open issues:

- Live OpenAI behavior still needs a user-provided `OPENAI_API_KEY`.
- CI, secret scanning, and dependency auditing are not wired yet.
- The golden set is synthetic and single-signal; mixed-signal and clean
  negative examples remain necessary.

Next up:

- Wire Ruff, mypy, pytest, the compact eval, secret scanning, and dependency
  auditing into GitHub Actions.
- When the API key is available, capture a controlled live-model accuracy,
  invalid-output, latency, fallback, and cost baseline.

## 2026-09-08 (Day 6)

Phase: 1–4 accelerated integration slice (14-day plan Days 6–14 locally)

Did:

- Added GitHub Actions jobs for Ruff, mypy, pytest, deterministic evals,
  prompt-injection gates, secret scanning, dependency audit, three Docker image
  builds, and Terraform format/validation.
- Added async SQLAlchemy/Alembic persistence for reviews, questions, interview
  sessions/turns, progress snapshots, knowledge items, retrieval events, and
  agent runs. The schema stores source/answer hashes and derived metadata, not
  raw code, finding evidence, or raw answers.
- Added PostgreSQL full-text + pgvector hybrid retrieval, optional OpenAI
  embeddings, local fallback, corpus seeding, and HNSW/FTS indexes.
- Added stateful interview turns and durable progress aggregation/snapshots.
- Expanded Streamlit into Review → Interview → Progress, with pasted/GitHub
  source modes and role handoff. Browser-verified the flow, validation states,
  public GitHub review, and 390px layout.
- Implemented the sole GitHub MCP boundary with exactly three annotated
  read-only tools, strict URL/ref/path validation, GET-only fixed-host HTTP,
  no redirects, timeouts, extension/binary checks, and tree/file/byte caps.
- Added hashed Redis embedding/retrieval caching, fail-open metrics, and
  `/runtime/cache`; deliberately did not cache source-bearing review responses.
- Added explicit privacy-reduced Langfuse spans for the request and every graph
  stage, model/token/fallback metadata, bounded sampling, redaction, disabled
  automatic IO capture, and graceful flushing.
- Added non-root backend/frontend/MCP images and five-service Compose with
  health-gated Postgres, Redis, MCP, FastAPI, and Streamlit startup.
- Added an unapplied Terraform module for Budget, VPC/security groups, ECR,
  ECS/Fargate, ALB/optional TLS, Cloud Map, private RDS/pgvector, private TLS
  ElastiCache, CloudWatch, and managed-secret injection.
- Reconciled PRD, architecture, cloud, security, cost, evaluation, README, and
  every touched folder's current-state memory.

Learned / decided:

- The remote MCP HTTP path successfully listed 10 files from public
  `pypa/sampleproject`; public repos need no token, while private verification
  waits for a user-owned read-only token.
- A real Compose migration created the pgvector schema and all five services
  became healthy. Two persisted synthetic reviews contained a 64-character
  code hash, line count, mode, and derived data only.
- One local correctness smoke measured ~111 ms cold and ~8.6 ms after the first
  Redis retrieval-cache hit (miss/write followed by hit); it is not yet a
  representative benchmark.
- Terraform 1.16.1 selected locked AWS provider 6.63.0 and validates without
  warnings. No AWS credentials were used and no resource was planned/applied.
- ECS injects only the password field of the RDS-managed secret; the backend
  assembles and URL-encodes the database URL in memory.
- Public tasks avoid NAT cost but accept ingress only from the ALB/calling
  service; RDS and Redis remain in isolated data subnets.

Verification:

- 57 tests passed; Ruff and mypy are clean.
- Deterministic eval `2026-09-07.v1` passes all thresholds with zero model cost.
- `detect-secrets` passes and `pip-audit` reports no known vulnerabilities.
- All three final images build; final application containers and dependencies
  report healthy.
- Terraform format check and provider-schema validation pass.
- `git diff --check` passes.

Open issues:

- Live OpenAI/Langfuse evidence needs user keys; private GitHub needs a scoped
  read token.
- Final `FeedbackReport`, adaptive follow-ups, mixed/negative evals, and the
  100–500 item knowledge corpus remain incomplete.
- Public authentication and daily model-spend limits are required before
  enabling a paid public endpoint.
- AWS plan/apply/deploy requires explicit account, region, budget, ingress/TLS,
  credentials, and teardown approval; no paid resource exists.

Next up:

- Implement the final structured feedback report and expand eval coverage with
  clean-negative, mixed-signal, interview-answer, and feedback-report cases.
- Then add public API authentication and enforce per-request/daily model spend
  ceilings before asking for credentialed provider and AWS checkpoints.

## 2026-09-08 (Day 7)

Phase: 3–4 feedback, public-safety, and cost-control checkpoint

Did:

- Added `GET /interview/{session_id}/feedback` and deterministic typed final
  reports for completed interviews: ranked strengths, genuinely repeated gaps,
  concrete practice tasks, bounded readiness summary, and up to five
  privacy-safe supporting findings.
- Extended both interview repositories to return privacy-reduced turn evidence
  and both review stores to read persisted findings without restoring raw code
  or finding evidence.
- Rendered the final report in Streamlit and reset its state correctly across
  new reviews/interviews.
- Added optional constant-time `X-Clutch-API-Key` protection for every FastAPI
  route except `/health`; required-but-missing configuration fails closed.
- Added conservative completion/embedding cost reservations with $0.10 per-call
  and $1.00 UTC-daily defaults, actual-token reconciliation, explicit custom
  model pricing, atomic Redis sharing, a safe `/runtime/spend` endpoint, and
  static fallback when budget blocks a provider call.
- Wired auth/spend settings through `.env.example`, Compose, and Terraform.
  Terraform now refuses to start public ECS tasks without an API-key secret ARN
  and injects that key only into backend and server-side Streamlit.

Learned / decided:

- Final feedback can be useful and fully reproducible without another model
  call; it should aggregate stored assessments and derived review metadata, not
  raw answers.
- A provider call reserves against the worst bounded output plus a conservative
  UTF-8-byte input estimate. Missing usage retains that reservation rather than
  undercounting spend.
- Built-in rates match the official OpenAI model pages checked on 2026-09-08:
  `gpt-5.4-mini` $0.75/$4.50 per million input/output tokens and
  `text-embedding-3-small` $0.02 per million input tokens. Other models require
  explicit configured rates.

Verification:

- Ruff and mypy pass; all 66 tests pass.
- `detect-secrets` passes and `pip-audit` reports no known vulnerabilities.
- Targeted auth tests cover valid, missing, and unconfigured keys; spend tests
  cover per-call/daily limits, pricing, reconciliation, and pre-provider static
  fallback.
- Terraform 1.16.1 format/init-without-backend/validate passes with locked AWS
  provider 6.63.0.
- Rebuilt backend/frontend images and recreated the healthy five-service
  Compose stack.
- Container end-to-end smoke completed review → all interview turns → feedback;
  the report had strengths/supporting findings and contained no raw-answer
  sentinel. `/runtime/spend` reported the configured $0.10/$1.00 ceilings and
  $0 used on the no-key static path.
- Browser verification rendered the report after one completed answer; at 390px
  document width equalled viewport width with the report visible.

Open issues:

- The eval set still needs clean-negative, mixed-quality, interview-answer, and
  feedback-report cases before expanding or adapting interview behavior.
- The knowledge corpus remains eight items rather than Phase 2's 100–500 target.
- Live OpenAI/Langfuse evidence needs user keys; private GitHub needs a scoped
  read-only token.
- User-account auth, rate/abuse limiting, report export, retention automation,
  and adaptive follow-ups remain post-baseline hardening.
- AWS plan/apply/deploy still requires the explicit account, region, budget,
  ingress/TLS, credentials, and teardown checkpoint. No paid resource exists.

Next up:

- Expand the deterministic eval dataset and runner with clean-negative,
  mixed-quality, interview-answer, and feedback-report coverage; record honest
  metric deltas.
- Then expand the knowledge corpus toward 100–500 curated items, keeping source
  attribution and retrieval baselines reproducible.

## 2026-09-08 (Day 8)

Phase: 2–3 retrieval corpus and eval-quality checkpoint

Did:

- Replaced independent finding-label arrays with atomic expected findings so
  ID, category, severity, and required citations are evaluated together.
- Expanded the deterministic review suite from eight positive-only examples to
  12 cases: seven focused positives, three clean negatives, and two mixed-signal
  snippets.
- Removed the speculative fallback “missing tests” finding. A snippet with no
  rule-specific issue now returns zero findings and the UI states that this is
  not proof of correctness; structured model output now also permits zero.
- Added three end-to-end interview fixtures covering weak, strong, and mixed
  answers. The runner executes all turns and final feedback, checks exact scores,
  strengths, recurring gaps, tasks, readiness, supporting findings, and proves a
  raw-answer sentinel never enters persisted records or the report.
- Published deterministic baseline `2026-09-08.v2`: every gated metric is 1.0,
  hallucinated-line rate is 0.0, and Retrieval Precision@3 is 0.444 while
  Recall@3/MRR remain 1.0.
- Converted the hard-coded knowledge tuple into validated package data and
  expanded it from eight to 30 items: 18 cited references, six role-aware
  rubrics, and six question-bank prompts across all finding categories.
- Added knowledge item type, roles, and seniority metadata to local and durable
  retrieval, plus Alembic migration `20260908_0002` for existing databases.
- Updated product, architecture, evaluation, README, and folder memory docs to
  reflect the new evidence and remaining limits.

Learned / decided:

- A clean-negative suite is necessary to catch false-positive behavior; missing
  repository context or tests must not be presented as a confirmed code defect.
- Retrieval Precision@3 should remain visible at 0.444. The current labels mark
  only known-relevant items, so inflating them would hide the need for graded
  relevance judgments over every returned candidate.
- Corpus growth now has a scalable schema. New items must add distinct evidence,
  role expectations, or interview value rather than duplicate text to hit a
  numeric target.

Verification:

- Ruff passes; mypy passes over 56 source files; all 67 tests pass.
- Eval `2026-09-08.v2` passes with 12 review, three injection, and three complete
  interview/report cases at $0 model cost.
- Alembic reports a linear migration chain ending at `20260908_0002`.
- `detect-secrets` passes and the network-enabled `pip-audit` reports no known
  vulnerabilities.

Open issues:

- The knowledge corpus is 30 items, still below Phase 2's 100–500 target.
- Retrieval evals need graded relevance for all top-three results, multi-file
  repository cases, and a controlled vector-only versus hybrid comparison.
- Live OpenAI/Langfuse evidence needs user keys; private GitHub needs a scoped
  read-only token.
- Adaptive follow-up generation remains deferred until broader eval evidence
  justifies another model call.
- AWS plan/apply/deploy still requires the explicit account, region, budget,
  ingress/TLS, credentials, and teardown checkpoint. No paid resource exists.

Next up:

- Expand the corpus from 30 toward 100 with distinct language, role, and rubric
  coverage while adding graded retrieval judgments for the new items.
- Then, at the user-credential checkpoint, capture controlled OpenAI/Langfuse
  baselines and verify a read-only private GitHub repository before considering
  adaptive interview behavior or AWS staging.

## 2026-09-08 (Day 9)

Phase: 2–4 retrieval-quality and commit-organization checkpoint

Did:

- Expanded the validated corpus from 30 to 60 distinct items: 36 cited
  references, 12 role-aware rubrics, and 12 question-bank prompts.
- Added explicit 0–3 relevance judgments for every current top-three retrieval
  result plus known relevant candidates that were not returned.
- Added nDCG@3, judgment coverage, and irrelevant-result rate alongside binary
  Precision@3, Recall@3, and MRR. Dataset version is now
  `2026-09-08.v3`.
- Used the graded metrics to identify a real ranking regression after corpus
  growth: shared `seed.clean_code` source-ID tokens and generic role words were
  outweighing issue-specific evidence.
- Removed source IDs from retrieval queries, filtered positive retrieval by
  finding category, removed common stop words, and requested a mix of reference,
  rubric, and question context.
- Added a bounded code-term extractor for zero-finding snippets. It ignores
  comments, extracts at most 40 identifier/literal terms, adds narrow SQL/error
  concepts, and never persists the derived query.
- Split the accumulated implementation into a dependency-ordered local commit
  series covering review contracts, data/runtime safeguards, RAG, agent/model
  orchestration, GitHub MCP, interview/progress, API/UI, eval/security gates,
  infrastructure, and documentation.

Learned / decided:

- Retrieval metrics must fail when corpus growth changes the top three to an
  unjudged item; defaulting unjudged results to irrelevant makes label drift
  visible instead of silently preserving a perfect score.
- Grades 2–3 count as relevant for binary metrics, while nDCG uses all grades.
  This preserves the useful distinction between marginal interview context and
  evidence directly applicable to the finding.
- Full source IDs are identifiers, not semantic query text. Their shared prefix
  created artificial similarity and must never affect ranking.
- Commits follow the feature dependency graph; no remote push was performed.

Verification:

- Ruff passes; mypy passes over 57 source files; all 72 tests pass.
- Eval `2026-09-08.v3` passes at $0 model cost: Precision@3 0.727, Recall@3
  0.649, MRR 1.0, nDCG@3 0.951, judgment coverage 1.0, and irrelevant-result
  rate 0.028. Finding, citation, question, interview, feedback, privacy, and
  injection gates remain perfect; hallucinated-line rate remains zero.

Open issues:

- The corpus is 60 items, still below the Phase 2 target of 100–500.
- Retrieval needs multi-file repository fixtures and a controlled lexical,
  vector-only, and hybrid comparison on the same judgments.
- Live OpenAI/Langfuse evidence and private GitHub verification require
  user-owned credentials.
- Adaptive interview follow-ups remain deferred until controlled model evals
  justify the extra model call.
- AWS staging remains behind the explicit account, region, budget, ingress/TLS,
  credential, and teardown checkpoint. No paid resource exists.

Next up:

- Add multi-file retrieval cases, then expand the corpus from 60 to at least 100
  without reducing judgment coverage.
- At the credential checkpoint, run controlled OpenAI/Langfuse/private-GitHub
  baselines before any adaptive interview or AWS deployment decision.
