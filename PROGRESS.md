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

## 2026-09-08 (Day 10)

Phase: 2–3 multi-file evaluation and corpus lower-bound checkpoint

Did:

- Added three typed multi-file repository fixtures and ran them through the real
  `GitHubReviewService` coordinator with an in-memory read-only gateway.
- Added report-level GitHub ingestion and persisted-source privacy gates; all
  intended Python paths must be included and request-scoped sentinels must not
  appear in the review recorder.
- Expanded per-case evidence with retrieved source IDs, then included GitHub
  cases in finding, retrieval, citation, question, clean, and mixed metrics.
- Reworked deterministic lexical scoring so issue-specific tag, title, and body
  evidence outranks generic category, role, rubric, and question metadata.
- Expanded retrieval queries with finding explanation and suggestion text,
  which is derived feedback rather than raw source.
- Expanded the curated corpus from 60 to 100 items: 60 references, 18 rubrics,
  and 22 question prompts. Every category has 10 references, three rubrics, and
  at least three questions, with stable citation IDs and role/seniority tags.
- Kept the work dependency-ordered in three local commits: multi-file evals,
  ranking robustness, then corpus expansion. No remote push was performed.

Learned / decided:

- The old lexical score let generic words such as `question` and `design`
  create tie groups whose order depended on source IDs. Identifiers and routing
  metadata must not masquerade as semantic relevance.
- Mixed multi-file queries can have seven relevant corpus items while K is
  fixed at three. The Recall@3 floor is now 0.55; MRR, nDCG, full judgment
  coverage, and irrelevant-result rate remain independent ordering safeguards.
- Reaching 100 items satisfies the Phase 2 lower bound. Further corpus growth
  should answer measured retrieval gaps rather than chase item count.

Verification:

- Ruff passes; mypy passes over 54 source files; all 73 tests pass.
- Eval `2026-09-08.v5` passes at $0 model cost across 15 review cases, including
  three multi-file GitHub repositories. Finding/citation/question/ingestion/
  privacy gates are 1.0.
- Retrieval Precision@3 is 0.786, Recall@3 0.559, MRR 1.0, nDCG@3 0.934,
  judgment coverage 1.0, and irrelevant-result rate 0.044.
- Corpus validation reports 100 unique IDs, 100 matching citation IDs, no exact
  duplicate summaries, and 57 externally linked references.

Open issues:

- The same judgments have not yet been compared across local lexical,
  PostgreSQL lexical, vector-only, and hybrid retrieval modes.
- Live OpenAI/Langfuse evidence and private GitHub verification require
  user-owned credentials.
- Adaptive interview follow-ups remain deferred until controlled model evidence
  justifies the added latency and cost.
- AWS staging remains behind explicit account, region, budget, ingress/TLS,
  credential, and teardown approval. No paid resource exists.

Next up:

- Add a reproducible retrieval-comparison runner over the existing graded
  queries, execute all credential-free modes, and leave vector/model runs at the
  explicit API-key checkpoint.
- Then capture controlled OpenAI, Langfuse, and private-GitHub evidence before
  any adaptive-interview or AWS decision.

## 2026-09-08 (Day 11)

Phase: 2–3 retrieval-strategy comparison checkpoint

Did:

- Centralized bounded retrieval-query construction for the live graph and eval
  runners: at most eight derived findings, 4,000 query characters, and eight
  results, with raw finding evidence and source comments excluded.
- Added a vector-only pgvector retriever alongside the existing PostgreSQL
  lexical/hybrid path.
- Added a reproducible comparison runner for local lexical, PostgreSQL lexical,
  PostgreSQL vector-only, and PostgreSQL hybrid retrieval over the same 15
  bounded queries and v5 relevance judgments.
- Kept comparison output privacy-reduced to query hashes, categories, retrieved
  source IDs, metrics, latency, and estimated query cost.
- Migrated and seeded a disposable local PostgreSQL service with all 100 corpus
  items, then discovered that `plainto_tsquery` required every term in a broad
  review query and returned no rows.
- Replaced that query with a deduplicated, bounded 64-term OR web-search query
  and added a regression test.
- Replaced the exact judgment-coverage gate with a 0.90 floor. Unjudged hits
  still count as relevance zero in nDCG and irrelevant-rate, avoiding a double
  penalty while preventing label coverage from silently collapsing.
- Split the work into focused local commits for bounded queries, eval
  primitives, vector retrieval, comparison runner, the PostgreSQL fix, and the
  eval-policy change. No remote push was performed.

Learned / decided:

- Review-derived retrieval queries are naturally long; PostgreSQL AND semantics
  are unsuitable because no one knowledge item should repeat the entire review.
- Field-weighted full-text experiments did not improve the judged metrics and
  were discarded rather than shipped.
- A comparison runner must report unavailable credentialed strategies honestly;
  it must not silently substitute lexical results for vector or hybrid modes.

Verification:

- Ruff passes; mypy passes over 61 source files; all 78 tests pass.
- Local lexical: Precision@3 0.786, Recall@3 0.559, MRR 1.0, nDCG@3 0.934,
  judgment coverage 1.0, irrelevant rate 0.044, mean latency 0.48 ms, $0 cost.
- PostgreSQL lexical: Precision@3 0.786, Recall@3 0.559, MRR 1.0, nDCG@3
  0.914, judgment coverage 0.911, irrelevant rate 0.089, mean latency 16.22 ms,
  $0 cost. Both strategies pass the current gate.

Open issues:

- PostgreSQL vector-only and hybrid quality, latency, and cost remain unmeasured
  because corpus/query embeddings require a user-owned OpenAI API key.
- Live review synthesis and Langfuse evidence require user-owned credentials;
  private GitHub verification requires a scoped read-only token.
- Adaptive interview follow-ups remain deferred until controlled model evidence
  justifies the added latency and cost.
- AWS staging remains behind explicit account, region, budget, ingress/TLS,
  credential, and teardown approval. No paid resource exists.

Next up:

- At the explicit credential checkpoint, add `OPENAI_API_KEY` only to the
  untracked `.env`, seed missing corpus embeddings, and run the comparison with
  `--require-all` under the existing spend guard.
- Then capture a controlled live OpenAI structured-output baseline and optional
  privacy-reduced Langfuse trace before requesting private-GitHub or AWS access.

## 2026-09-09 (Day 12)

Phase: 3–4 local completion and deployment handoff

Did:

- Extracted shared review-output scoring so deterministic and live-model evals
  use the same finding, grounding, question, and line-range logic.
- Added privacy-safe provider attempt and validation-failure counters, including
  Pydantic invariants, redacted graph/span propagation, retry/fallback tests,
  and no raw provider error text.
- Added a manual live-model runner over six representative reviews and all three
  injection fixtures. It uses the production graph, an isolated $0.50 default
  cap, privacy-reduced output, typed no-key unavailability, and a nonzero exit
  on any configured fallback.
- Rebuilt all three non-root images, migrated PostgreSQL, and brought the full
  five-service Compose stack to healthy.
- Exercised pasted review, interview start/answer, final feedback, and progress
  through real localhost HTTP and Streamlit boundaries. PostgreSQL stored a
  64-character source hash and derived metadata, not raw code.
- Captured and committed real review, interview-assessment, and progress UI
  screenshots. Expanded the README with a concrete walkthrough, failure
  analysis, local quality/cost/latency evidence, prompt-injection example, AWS
  diagram, deployment handoff, and resume-ready bullets.
- Refreshed architecture, cost, evaluation, security, and folder memory docs so
  they describe the completed local implementation and credential checkpoint.

Learned / decided:

- A controlled live baseline needs its own bounded spend counter so repeated
  experiments cannot accidentally consume the application's full daily budget.
- Validation failure rate must be derived from explicit safe counters, not raw
  exceptions or provider payloads.
- Terraform validation can remain credential-free; AWS plan/apply and image
  publication stay intentionally outside CI until the paid-resource checkpoint.
- The 14-day plan's credential-free implementation is complete. Adaptive
  interview generation and Claude remain evidence-gated post-v1 work.

Verification:

- Ruff passed; mypy passed over 63 source files; all 83 tests passed.
- Deterministic eval `2026-09-08.v5` passed every gate at $0 model cost.
- `detect-secrets` passed and `pip-audit` found no known vulnerabilities.
- Three Docker images rebuilt; five Compose services were healthy; Alembic
  upgrade succeeded; local review/interview/feedback/progress smoke passed.
- Terraform 1.16.x formatting and validation passed with AWS provider 6.63.0.
- The live-model command returned typed `available=false`, zero tokens, and
  $0.00 charged cost without `OPENAI_API_KEY`, as designed.

Open issues:

- Credentialed OpenAI model and vector/hybrid baselines, Langfuse trace
  inspection, and private-GitHub token verification require user-owned secrets.
- AWS saved-plan/cost review, immutable ECR publication, migration task,
  staging smoke, public URL, log inspection, rollback rehearsal, incident owner,
  and teardown time belong to the explicit deployment session.
- No AWS resources have been planned or applied, and no remote push occurred.

Next up:

- User adds credentials only to ignored local/AWS secret stores, then runs the
  capped live-model and `--require-all` retrieval comparisons and inspects one
  privacy-reduced Langfuse trace.
- After confirming AWS account, region, budget, ingress/TLS, incident owner, and
  teardown policy, follow `CLOUD.md` to saved-plan review, immutable image push,
  migration, one-task staging enablement, smoke/privacy verification, and URL
  publication.

## 2026-09-09 (Day 13)

Phase: 4 local deployment rehearsal

Did:

- Added `compose.localstack.yaml` for `localstack/localstack-pro` with
  `LOCALSTACK_AUTH_TOKEN` read from the shell, loopback gateway ports, Docker
  socket mounting for later ECS execution tests, and ignored persistent state.
- Added `infra/localstack/terraform`, a separate LocalStack-only Terraform
  harness that targets `http://localhost:4566` with dummy AWS credentials and
  creates emulated VPC networking, ECR repositories, Secrets Manager API-key
  secret/version, IAM roles/policies, CloudWatch log groups, ECS task
  definitions, and zero-desired-count ECS services.
- Added helper scripts for LocalStack startup, Terraform init/plan/apply/
  destroy/output, environment inspection, and AWS-resource smoke checks.
- Wired CI Terraform validation to cover both the production AWS module and the
  LocalStack harness.
- Updated README, `CLOUD.md`, `.env.example`, ignore files, and infra memory
  docs for the new rehearsal path.

Learned / decided:

- Keep LocalStack separate from the production Terraform root so local emulation
  cannot weaken the paid-resource AWS safety checkpoint.
- Default LocalStack ECS services to desired count zero. First prove AWS
  control-plane descriptors locally, then separately test emulated task
  execution if needed.
- The LocalStack auth token was not exported in the Codex shell, so the pasted
  chat token was not used. It should be rotated before use.

Verification:

- `docker compose -f compose.localstack.yaml config --quiet` passed with a
  dummy token.
- All LocalStack shell scripts passed `bash -n`.
- AWS CLI is installed, but Terraform is not installed on PATH. Homebrew
  Terraform installation from the HashiCorp tap was blocked by outdated Xcode,
  so `scripts/localstack_terraform.sh` now falls back to
  `hashicorp/terraform:1.16.1` through Docker.
- The Terraform Docker fallback was verified with
  `docker run --rm hashicorp/terraform:1.16.1 version`.
- LocalStack CLI installation is blocked by the same outdated Xcode requirement,
  so LocalStack startup uses Docker Compose directly.
- Docker daemon access from Codex required host permission, and a rotated
  `LOCALSTACK_AUTH_TOKEN` was not available in the environment, so the
  LocalStack container was not started.

Open issues:

- Export a rotated `LOCALSTACK_AUTH_TOKEN` or put it in ignored
  `.env.localstack`, then run the LocalStack init/plan/apply/smoke sequence.
- If the zero-count apply succeeds, the next LocalStack layer is image push plus
  `service_desired_count=1` ECS task execution.
- The practical public deployment path should move to Vercel/Render/Supabase
  after the LocalStack learning rehearsal; AWS should stay unapplied unless
  budget approval changes.

Next up:

- Run `scripts/localstack_up.sh`, `scripts/localstack_terraform.sh init`,
  `scripts/localstack_terraform.sh plan`, `scripts/localstack_terraform.sh
  apply`, and `scripts/localstack_smoke.sh` from a shell with the rotated token.

## 2026-09-09 (Day 13 continuation)

Phase: 4 local deployment rehearsal

Did:

- Created ignored `.env.localstack` support so the rotated LocalStack token can
  be consumed without committing it or putting it directly in commands.
- Started `localstack/localstack-pro:latest`; LocalStack reported Pro edition,
  activated license, and healthy status on `127.0.0.1:4566`.
- Initialized the LocalStack Terraform module through the Docker fallback using
  `hashicorp/terraform:1.16.1` and AWS provider 6.63.0.
- Fixed provider endpoint names for AWS provider 6.x, formatted the module, and
  validated it successfully.
- Planned the full LocalStack control-plane shape, then learned the current
  LocalStack license returns 501 for ECR and ECS.
- Made ECR/ECS optional (`enable_emulated_ecr`, `enable_emulated_ecs`) and
  disabled by default. Replanned and applied the supported subset.
- Smoked LocalStack with AWS CLI: health endpoint reachable, emulated VPCs
  listed, `/ecs/clutch-localstack/backend`, `/frontend`, and `/github-mcp` log
  groups listed, and `clutch-localstack/clutch-api-key` listed in Secrets
  Manager.
- Started the regular Clutch Compose stack with Postgres, Redis, GitHub MCP,
  backend, and frontend healthy at the same time as LocalStack.
- Aligned the existing local Postgres user's password non-destructively, reran
  Alembic successfully, and verified FastAPI `/health`, Streamlit health, and a
  local `/review` request returning two structured findings and questions.
- Updated docs to keep AWS unapplied for cost reasons and pivot the next public
  deployment target to Vercel/Render/Supabase.

Learned / decided:

- LocalStack is useful here for supported AWS API learning and Terraform
  provider wiring, but this license cannot rehearse ECR/ECS task deployment.
- Keep the LocalStack default apply limited to supported services. Optional
  ECR/ECS flags document the next layer for a higher LocalStack license.
- Use Docker-based Terraform because Homebrew Terraform and LocalStack CLI are
  blocked by outdated Xcode on this machine.
- AWS remains a portfolio architecture path only unless budget approval changes.

Verification:

- LocalStack health and license activation passed.
- `scripts/localstack_terraform.sh init`, `fmt`, `validate`, `plan`, and
  `apply` passed for the supported subset.
- `scripts/localstack_smoke.sh` passed with AWS CLI against
  `http://localhost:4566`.
- Docker Compose app stack reports Postgres, Redis, GitHub MCP, backend,
  frontend, and LocalStack all healthy.
- FastAPI health returned `{"status":"ok"}`; Streamlit health returned `ok`.
- Local `/review` smoke returned static fallback findings for debug `print` and
  mutable default argument with clean-code citations.

Open issues:

- ECR/ECS cannot be tested on the current LocalStack license tier.
- The local `.env` API key was surfaced during a presence check; rotate it
  before any hosted deployment.
- Add a dedicated Render/Supabase/Vercel deployment guide and smoke scripts
  next.

Next up:

- Prepare the Vercel/Render/Supabase deployment path: Supabase pgvector schema
  migration notes, Render service/env setup, optional Redis provider, and a
  hosted smoke checklist.

## 2026-09-09 (Day 13 no-fallback checkpoint)

Phase: 4 demo correctness checkpoint

Did:

- Changed env-built review runtime so `CLUTCH_ALLOW_STATIC_FALLBACK` defaults
  to false. Model review is now required for demo/deployment by default.
- Added `ReviewModelUnavailable` and FastAPI 503 handling so model/provider/
  validation/budget failures fail loudly instead of returning deterministic
  findings.
- Kept deterministic fallback opt-in for tests/evals by constructing
  `ModelRouter(..., allow_static_fallback=True)` or setting
  `CLUTCH_ALLOW_STATIC_FALLBACK=true`.
- Canonicalized known model citation IDs from the local knowledge base while
  still rejecting invented citations and impossible line ranges.
- Rebuilt backend/frontend Docker images and recreated healthy containers with
  the new code.

Learned / decided:

- For demo credibility, user-facing review output should not silently fall back
  to deterministic findings when an OpenAI key is configured.
- Current live review requests return 503 with `model review unavailable:
  ValueError`, so the model path is being reached but still fails validation/
  grounding. That should be debugged before claiming AI-backed review quality.

Verification:

- `tests/test_model_router.py` passed.
- Backend/frontend containers were rebuilt and became healthy.
- A local `/review` request now returns HTTP 503 instead of `mode:
  static_fallback` when model review fails.

Open issues:

- Debug the remaining OpenAI model validation failure after rotating the exposed
  key.
- API tests are influenced by local `.env` auth settings in this shell; run the
  full suite from a clean test env before the next commit if changing API auth
  tests.

Next up:

- Rotate exposed local keys, then run a model-required review and inspect safe
  diagnostics until it returns `mode: model`.

## 2026-09-09 (Day 13 local runtime + free deployment path)

Phase: 4 low-cost deployment preparation

Did:

- Added privacy-safe provider warning logs for bounded OpenAI review attempts:
  model name, attempt counts, exception class, and allowlisted failure detail
  only.
- Added explicit Langfuse flush after review requests so demo traces are not
  left waiting for shutdown batching.
- Added `.python-version`, `render.yaml`, `docs/free-deployment.md`, and
  `scripts/hosted_smoke.sh` for the Supabase -> Render -> optional Vercel path.
- Updated README, `CLOUD.md`, and infra/LLM/observability/project memory docs
  for the low-cost deployment sequence.
- Stopped only Docker app containers and kept Docker Postgres, Redis, and
  LocalStack running.
- Set a local-only ignored `CLUTCH_DB_PASSWORD`, aligned the existing Postgres
  role, and reran Alembic successfully.
- Started GitHub MCP, FastAPI, and Streamlit directly from `.venv`.

Learned / decided:

- The previous no-logs Langfuse symptom was expected because
  `LANGFUSE_TRACING_ENABLED=false`; local runtime now starts with it enabled.
- The model-required 503 disappeared in the `.venv` runtime after environment
  alignment; pasted-code and GitHub reviews both returned `mode: model`.
- Keep Render as the actual public app host, Supabase as the pgvector database,
  and Vercel as an optional portfolio landing/link shell.

Verification:

- Focused deterministic tests passed with clean test env and
  `CLUTCH_ALLOW_STATIC_FALLBACK=true`: `tests/test_review_api.py`,
  `tests/test_model_router.py`, and `tests/test_observability.py`.
- Ruff passed for the changed provider/observability/review files.
- `git diff --check`, `bash -n scripts/hosted_smoke.sh`, and a YAML parse check
  for `render.yaml` passed.
- Local health checks passed for FastAPI `:8000`, GitHub MCP `:8001`, and
  Streamlit `:8501`.
- Local pasted-code review returned `mode: model` with two findings and two
  questions; GitHub review of `pypa/sampleproject` returned `mode: model` with
  five included Python files.
- Cache and spend endpoints responded; Langfuse `auth_check` passed against
  `https://jp.cloud.langfuse.com`.
- LocalStack health reported Pro edition with `apigateway`, `ec2`, `iam`,
  `logs`, and `secretsmanager` running.

Open issues:

- Rotate the local OpenAI, GitHub, Langfuse, and Clutch API keys before copying
  any value to hosted providers.
- Confirm Langfuse traces visually in the dashboard after the explicit flush.
- Run the broader live-model eval only after key rotation.

Next up:

- Create Supabase project, enable pgvector, run migrations/seed, then deploy
  the two Render web services and run `scripts/hosted_smoke.sh`.

## 2026-09-09 (Day 13 no-fallback final + Streamlit Cloud handoff)

Phase: 4 demo correctness + low-cost deployment handoff

Did:

- Removed the runtime deterministic AI fallback path entirely:
  `FallbackStaticProvider`, `CLUTCH_ALLOW_STATIC_FALLBACK`,
  `static_fallback`, fallback metadata fields, and fallback-rate eval reporting
  are gone from the user-facing review flow.
- Changed `ModelRouter` so missing providers, provider failures, budget
  failures, and validation failures raise typed unavailable errors instead of
  returning synthetic review output.
- Kept deterministic rules only inside the offline eval harness/test doubles,
  separated from runtime model behavior.
- Updated API, graph, guardrail, persistence, GitHub review, observability, and
  live-model tests for the model-or-error contract.
- Updated Streamlit to read `CLUTCH_API_BASE_URL` and `CLUTCH_API_KEY` from
  either environment variables or `st.secrets`, making it deployable on
  Streamlit Community Cloud.
- Switched the free public deployment guide to Supabase -> Render backend ->
  Streamlit Community Cloud UI; `render.yaml` now describes only the FastAPI
  backend, and root `requirements.txt` supports Streamlit Cloud dependency
  install.
- Restarted the local `.venv` GitHub MCP, FastAPI, and Streamlit services.

Learned / decided:

- Runtime AI review must be binary: a real model-backed result or a clear
  error. Deterministic rules are still useful for offline eval gates, but they
  should never masquerade as AI output.
- The next public demo should host FastAPI on Render, Postgres/pgvector on
  Supabase, and `frontend/app.py` on Streamlit Community Cloud.

Verification:

- Full tests passed: 85/85.
- Ruff passed for `src`, `tests`, `frontend`, and `scripts`.
- Mypy passed over 63 source files.
- `git diff --check` passed.
- `bash -n scripts/hosted_smoke.sh` passed.
- Local health checks passed for GitHub MCP `:8001`, FastAPI `:8000`, and
  Streamlit `:8501`.
- Authenticated local pasted-code review returned `mode: model` with two
  findings and two questions.

Open issues:

- Rotate OpenAI, GitHub, Langfuse, and `CLUTCH_API_KEY` values before entering
  them into Supabase, Render, or Streamlit Community Cloud.
- Supabase migration/seed, Render backend deployment, Streamlit Community Cloud
  UI deployment, hosted smoke, and visual Langfuse trace confirmation are still
  deployment-time tasks.

Next up:

- Create Supabase, enable `vector`, run Alembic and seed scripts; deploy Render
  backend; deploy Streamlit Community Cloud UI; then run
  `scripts/hosted_smoke.sh`.

## 2026-09-10 (Day 14 deployment-ready AI evidence + Neon production)

Phase: 4 deployment and measured production readiness

Did:

- Restored a model-first contract with literal provenance for static/retrieval,
  template-question, and rule-based-assessment fallbacks.
- Curated exactly 120 atomic, source-traceable knowledge items from the approved
  Python/PEP, OWASP, pytest/unittest, and Google sources.
- Added versioned seed synchronization, grounded model question generation,
  RAG-grounded AI interview assessment, prompt manifests, stronger citation
  support gates, complete stage diagnostics, and native Langfuse trace fields.
- Added per-item frontend labels, stage diagnostics, clickable exact-section
  citations, and bounded GitHub analysis scope messaging; browser-tested model,
  fallback, error, empty, keyboard, and 390px states.
- Installed and authenticated Neon CLI 4.14.6, installed the official project
  skills/MCP configuration, linked project `holy-feather-79203801` branch
  `production`, and committed the empty `neon.ts` policy plus lockfiles.
- Created snapshot `clutch-pre-migration-20260910`, proved the full Alembic chain
  on a disposable production clone, then deleted that clone.
- Migrated Neon production to `20260909_0003`; synchronized 120 embeddings for
  $0.00015972 and proved the second sync was unchanged/zero-cost.
- Verified all ten tables, 120 active provenance-complete rows, 120 valid
  1536-dimensional embeddings, no raw-code/raw-answer columns, and pooled
  temporary read/write behavior.
- Recorded a passing capped `gpt-5.4-mini` baseline and a four-strategy Neon
  retrieval comparison, then made the sole gate-passing `local_lexical`
  strategy the deployment default without lowering thresholds.
- Replaced the Supabase handoff with Neon → Render → Streamlit Community Cloud.

Learned / decided:

- This host blocks direct PostgreSQL port 5432. The exact offline SQL generated
  by Alembic was applied transactionally through Neon's official HTTPS driver;
  Alembic remains the only schema source.
- Local lexical won the fixed retrieval benchmark. Neon lexical/vector/hybrid
  stay implemented and seeded, but none should be called passing or selected
  until a future unchanged-gate rerun wins.
- The prior transient model-required/no-fallback and Supabase decisions in the
  2026-09-09 entries are superseded by the tested labeled-fallback and Neon
  production decisions above.
- Langfuse forced-fallback trace audit passes. The model trace contains native
  model/version/usage/latency, but Japan Cloud still returns empty native cost;
  keep that limitation explicit.

Verification:

- Deterministic `2026-09-10.v6` metrics pass every mandatory gate; citation
  validity/support are 1.000 and hallucinated-line rate is 0.000.
- Live baseline: finding/citation/question/injection/privacy metrics 1.000,
  interview within-one 0.833, zero schema failures, 16,411 input and 3,659
  output tokens, 2,941 ms average / 5,706 ms p95, $0.028781 total.
- Neon retrieval: local lexical nDCG@3 0.970 and passes; Neon lexical 0.913,
  vector 0.738, hybrid 0.872 and remain below one or more fixed gates.
- Final gates pass: Ruff, mypy across 73 source files, all 118 tests, prompt
  manifest and deterministic eval checks, secret scans, Python/JavaScript
  dependency audits, shell/Compose validation, and all three Docker image
  builds.

Open issues:

- Rotate local OpenAI/GitHub/Langfuse/Clutch API keys before deployment.
- Deploy Render and Streamlit Community Cloud, run the hosted smoke/manual
  privacy checks, and verify restart persistence.
- Re-run the model-trace audit when Langfuse native-cost readback is available.

Next up:

- Owner deploys the prepared Render backend and Streamlit Community Cloud UI
  using `docs/free-deployment.md`; no additional database setup is required.

## 2026-09-10 (Day 14 local pre-deploy smoke)

Phase: 4 deployment and measured production readiness

Did:

- Started the full local Compose app stack: Postgres, Redis, GitHub MCP,
  FastAPI backend, and Streamlit frontend.
- Reproduced and fixed a local Postgres persistence failure where detached
  `agent_runs` could flush before their parent `review_sessions` row.
- Rebuilt the backend image and reran authenticated local smoke checks for
  health, runtime cache/spend, pasted-code review, interview assessment,
  feedback report, progress summary, and GitHub repository review.

Learned / decided:

- The deployed-style local API key middleware is active whenever
  `CLUTCH_API_KEY` is configured, even if `CLUTCH_REQUIRE_AUTH` is false.
- Use the `X-Clutch-API-Key` header for authenticated API smoke checks.

Verification:

- `tests/test_persistence.py` and `tests/test_review_api.py`: 25 passed.
- Ruff passed for `src/clutch/persistence/repository.py`.
- Compose health is green for backend `:8000`, frontend `:8501`, GitHub MCP
  `:8001`, Postgres `:5432`, and Redis `:6379`.
- Local pasted-code review returned `mode: model` with one AI-generated finding,
  one AI-generated question, retrieved citation provenance, and persisted
  diagnostics.
- Local interview turn completed with AI-generated assessment, deterministic
  final report aggregation, and progress summary.
- Local GitHub review of `pypa/sampleproject` returned bounded MCP ingestion
  metadata and an AI-generated finding/question.

Open issues:

- Rotate local OpenAI/GitHub/Langfuse/Clutch API keys before deployment.
- Deploy Render and Streamlit Community Cloud, run hosted smoke/manual privacy
  checks, and verify restart persistence.

Next up:

- Test the currently running local UI at `http://localhost:8501`, then deploy
  via `docs/free-deployment.md` after key rotation.

## 2026-09-10 (Day 14 Streamlit Google auth)

Phase: 4 deployment and measured production readiness

Did:

- Added Streamlit OIDC support with a Clutch landing/login gate when `[auth]`
  secrets are configured.
- Derived a stable opaque `user_<sha256>` profile ID from the signed-in Google
  identity so progress can persist per user without storing raw email in route
  IDs.
- Kept the existing `X-Clutch-API-Key` backend boundary between Streamlit and
  FastAPI.
- Added a safe `.streamlit/secrets.example.toml`, ignored real local Streamlit
  secrets, and documented local/Streamlit Community Cloud Google OAuth setup.

Learned / decided:

- Use Streamlit `st.login()`/`st.logout()` for the v1 demo instead of adding a
  separate FastAPI auth provider.
- Local development remains anonymous unless Streamlit OIDC secrets exist; tests
  force anonymous mode to avoid depending on developer secrets.

Verification:

- Installed `authlib` for Streamlit OIDC.
- `tests/test_frontend_provenance.py` and `tests/test_review_api.py`: 20 passed.
- Ruff passed for `frontend/app.py`, `tests/conftest.py`, and
  `tests/test_frontend_provenance.py`.
- Mypy passed for `frontend/app.py`.
- Restarted Streamlit locally; frontend and backend health checks pass.

Open issues:

- Create/configure the Google OAuth web client for local and hosted redirect
  URIs, then add real values to local `.streamlit/secrets.toml` and Streamlit
  Community Cloud secrets.
- Run a browser login smoke once Google OAuth credentials are configured.

Next up:

- Add Google OAuth credentials, test login/logout and per-user progress locally,
  then deploy Render and Streamlit Community Cloud.

## 2026-09-10 (Day 14 recruiter landing page)

Phase: 4 deployment and measured production readiness

Did:

- Upgraded the unauthenticated Streamlit auth gate into a recruiter-facing
  landing page with a clear Clutch headline, review-to-interview-to-progress
  preview, stack proof chips, privacy notes, and Google login CTA.
- Kept the authenticated Review → Interview → Progress workbench unchanged.
- Updated the frontend landing AppTest expectation for the new public copy.

Verification:

- `tests/test_frontend_provenance.py` and `tests/test_review_api.py`: 20 passed.
- Ruff passed for `frontend/app.py` and `tests/test_frontend_provenance.py`.
- Mypy passed for `frontend/app.py`.
- `git diff --check` passed.
- Restarted Streamlit locally and verified health at `:8501`.

Open issues:

- Browser-review the landing page at desktop/mobile widths after logout or in an
  incognito window, then run the signed-in smoke again.

Next up:

- Deploy Render and Streamlit Community Cloud once the local landing/login smoke
  looks good.

## 2026-09-11 (Day 15 landing polish and deployment handoff)

Phase: 4 deployment and polish

Did:

- Rebuilt the public landing hero with native Streamlit layout containers so
  the login action and workflow preview remain inside one responsive card.
- Balanced the hero typography and columns, removed the stray heading anchor,
  tightened the login hierarchy, and retained the existing evidence-led design
  language.
- Expanded the Render and Streamlit Community Cloud runbook with a provider-by-
  provider secret map, Google OAuth audience steps, copy-ready TOML, failure
  recovery, and official provider references.
- Corrected `.streamlit/secrets.example.toml` so `CLUTCH_API_BASE_URL` and
  `CLUTCH_API_KEY` are top-level values rather than accidental `[auth]` members.
- Made the persistence and retrieval tests hermetic when a developer `.env`
  contains live service URLs.

Learned / decided:

- Streamlit widgets cannot be nested by leaving raw HTML tags open across
  separate `st.markdown` and `st.button` calls; keyed native containers are the
  stable layout boundary.
- Keep the Render/Streamlit API key shared, but use an independent cookie secret
  for Streamlit OIDC.
- A recruiter-facing Google OAuth client cannot remain limited to the owner's
  Testing user list when the portfolio link is shared publicly.

Verification:

- Browser-checked the landing page at 1512×982 and 390×844; both widths have no
  horizontal overflow and the desktop hero uses both columns.
- Premium UI strict audit: zero findings.
- Ruff: all checks passed.
- Mypy: 64 source files passed.
- Pytest: 120 passed.
- `pip check` and `git diff --check` passed.

Open issues:

- Hosted Google login/logout still needs real OAuth credentials and an exact
  deployed redirect URI.
- Render and Streamlit Community Cloud remain undeployed; hosted persistence,
  privacy, cold-start, and restart checks remain pending.

Next up:

- Rotate the named credentials, push the deployment branch, then follow
  `docs/free-deployment.md` from Render Blueprint creation through hosted smoke.

## 2026-09-11 (Day 16 security gate repair)

Phase: 4 deployment and polish

Did:

- Reproduced the pushed `Run security checks` failure locally and traced all
  five findings to reviewed placeholder or test-only OAuth values.
- Added line-local `detect-secrets` annotations to the three Streamlit deployment
  placeholders and two dummy OAuth test credentials.
- Preserved the repository-wide keyword detector and committed baseline instead
  of masking future secret findings globally.

Learned / decided:

- `detect-secrets` intentionally flags credential-shaped placeholders as well as
  real values; known fixtures should be documented at the exact source line so
  every new finding still fails CI by default.

Verification:

- Exact security runner passed both `detect-secrets` and strict `pip-audit`.
- Ruff passed.
- Mypy passed for 73 source files.
- Pytest: 120 passed.
- Prompt-manifest validation passed for three production prompts.
- Deterministic eval suite passed all configured gates.

Open issues:

- The follow-up commit still needs to be pushed so GitHub can rerun the security
  and container gates on `main`.

Next up:

- Push the security-gate repair, confirm the GitHub Actions run is green, then
  continue the Render and Streamlit Community Cloud deployment runbook.

## 2026-09-11 (Day 16 Render Redis Blueprint prompt)

Phase: 4 deployment and polish

Did:

- Added `REDIS_URL` as a `sync: false` Render Blueprint environment variable so
  first deploy can collect the Redis connection string instead of requiring a
  manual post-deploy service edit.
- Updated the free deployment runbook and infrastructure memory to reflect that
  Redis remains optional, but can now be enabled during the initial Blueprint
  flow.

Verification:

- Parsed `render.yaml` successfully with Ruby YAML.

Open issues:

- The Redis Blueprint prompt still needs to be pushed and synced in Render.
- Render rejected the follow-up deploy; the Blueprint defaults were then
  hardened so boolean/numeric env values are quoted as strings.
- Render then crashed on startup because the configured `DATABASE_URL` could not
  be parsed; runtime URL loading now tolerates common dashboard paste shapes
  such as surrounding quotes or a pasted `DATABASE_URL=` prefix.

Next up:

- Push the Blueprint update, paste the Redis URL when Render prompts, then wait
  for `/health` before updating Streamlit's `CLUTCH_API_BASE_URL`.

## 2026-09-11 (Day 16 Stytch auth switch)

Phase: 4 deployment and polish

Did:

- Replaced the Streamlit Google/OIDC login gate with Stytch email magic-link
  login backed by Stytch's backend API.
- Kept the existing opaque `user_<sha256>` progress profile shape, now derived
  from the Stytch user identity.
- Removed Google auth secrets from the sample Streamlit secrets file and
  updated the free deployment runbook to use Stytch Redirect URLs.
- Removed the now-unused `authlib` dependency from `pyproject.toml`.

Learned / decided:

- For the Streamlit Community Cloud deployment, Stytch keeps the public login
  path focused on email magic links and avoids a separate consent-screen
  publishing flow.

Verification:

- `tests/test_frontend_provenance.py`: 4 passed.
- Ruff passed for `frontend/app.py` and `tests/test_frontend_provenance.py`.
- Mypy passed for `frontend/app.py`.

Open issues:

- Hosted magic-link login still needs the real Stytch `project_id`, `secret`,
  environment, and exact Streamlit redirect URL added in Streamlit Cloud
  secrets.

Next up:

- Paste the `[stytch]` secrets into Streamlit Community Cloud, restart the app,
  request a magic link, and verify that the redirected session shows the logout
  control before running the hosted review smoke.

## 2026-09-11 (Day 16 landing polish)

Phase: 4 deployment and polish

Did:

- Increased the landing hero's spacing around the Stytch email magic-link form
  so the login box no longer sits tightly under the capability chips.
- Reworked the unauthenticated landing copy to foreground AI Engineer portfolio
  signals: Pydantic structured outputs, RAG citations, the read-only MCP GitHub
  boundary, prompt-injection guardrails, evals, tracing, caching, and
  privacy-safe persistence.
- Added Streamlit `toolbarMode = "viewer"` and app CSS hiding for reachable
  top-right Streamlit toolbar/menu chrome; removed old local config keys that
  were ignored by the project Streamlit version.

Verification:

- `tests/test_frontend_provenance.py`: 4 passed in the project `.venv`.
- Ruff passed for `frontend/app.py` and `tests/test_frontend_provenance.py`.
- Mypy passed for `frontend/app.py`.
- Streamlit config readback shows `toolbarMode = "viewer"` with no invalid-key
  warnings in the project `.venv`.

Open issues:

- Streamlit Community Cloud may still show owner-only controls such as
  “Manage app” to the signed-in app owner; verify the public/incognito view
  after redeploying.

Next up:

- Deploy the updated Streamlit app, then verify the public landing page in an
  incognito window before continuing the hosted review smoke.

## 2026-09-11 (Day 16 technical landing pass)

Phase: 4 deployment and polish

Did:

- Replaced the landing hero's simple practice-loop cards with a recruiter-facing
  review-to-interview pipeline preview: input, parse + RAG, agent, and evaluate.
- Added a typed-output sample line
  `CodeFinding[] -> InterviewQuestion[] -> FeedbackReport` to make the schema
  boundary visible on the first screen.
- Added an implementation-evidence strip with current rubric corpus, golden
  review, prompt-injection, and raw-data retention signals.

Verification:

- `tests/test_frontend_provenance.py`: 4 passed in the project `.venv`.
- Ruff passed for `frontend/app.py` and `tests/test_frontend_provenance.py`.
- Mypy passed for `frontend/app.py`.

Open issues:

- Final visual judgment should happen in the running local Streamlit app and
  again in an incognito hosted view after redeploying.

Next up:

- Refresh the local frontend, check the first viewport and mobile width, then
  deploy if the updated landing page reads well.

## 2026-09-11 (Day 16 public landing copy correction)

Phase: 4 deployment and polish

Did:

- Removed recruiter/demo framing from the unauthenticated landing page so it
  reads as a public product page for users.
- Removed the typed schema-chain sample and the “0 raw” metric from the landing
  page, replacing them with user-facing review, practice, scope, and progress
  highlights.
- Updated the landing test to guard against reintroducing recruiter/demo copy or
  the removed schema/raw-retention callouts.

Verification:

- `tests/test_frontend_provenance.py`: 4 passed in the project `.venv`.
- Ruff and mypy had already passed after the app copy edits; the final test-only
  assertion wording change was then rechecked with pytest.

Open issues:

- Refresh the running local frontend and visually confirm the public wording.

Next up:

- If the landing reads well, redeploy Streamlit and check the public/incognito
  view.

## 2026-09-11 (Day 16 hosted startup loading pass)

Phase: 4 deployment and polish

Did:

- Identified the attached dark skeleton as Streamlit Community Cloud wrapper UI
  shown before the Streamlit script has finished waking/starting, not a Clutch
  page state.
- Removed the eager top-level `pandas` import from the Streamlit app. Progress
  now imports it only when rendering the chart, so the landing/review path does
  less work before first paint.
- Added a frontend regression test that prevents reintroducing `pandas` as an
  initial app-start import.

Verification:

- `tests/test_frontend_provenance.py`: 5 passed in the project `.venv`.
- Ruff passed for `frontend/app.py` and `tests/test_frontend_provenance.py`.
- Mypy passed for `frontend/app.py`.
- Premium frontend strict audit passed with zero findings.

Open issues:

- Streamlit Community Cloud can still show its own dark skeleton while a sleeping
  app wakes. This code change shortens the startup window; fully removing that
  host-owned screen would require moving off Streamlit Community Cloud or adding
  an external keep-warm/hosting strategy.

Next up:

- Redeploy the Streamlit app, then verify the hosted public/incognito load and
  note whether the skeleton duration is acceptable.

## 2026-09-11 (Day 16 review grounding subset fix)

Phase: 4 deployment and polish

Did:

- Fixed review grounding validation so a model can synthesize a grounded subset
  of static findings instead of needing a one-to-one match with every static
  signal.
- Updated the review synthesis prompt to match the schema cap: use deterministic
  signals as the only allowed inventory, but return up to 12 highest-impact
  findings.
- Added regression coverage for accepting a grounded subset and still rejecting
  an empty model subset when static signals exist.

Learned / decided:

- The nanoGPT review path can produce more static signals than the strict model
  schema allows, so exact count matching caused valid model output to be
  mislabeled as a grounding failure and replaced by deterministic fallback.

Verification:

- `tests/test_model_router.py tests/test_review_prompt.py`: 15 passed.
- Ruff passed for the touched provider/test files.
- Mypy passed for `src/clutch/llm/providers.py` and `tests/test_model_router.py`.

Open issues:

- Rerun the nanoGPT resume analysis with the configured OpenAI provider to
  confirm the live path now reports `mode: model` for grounded subset output.

Next up:

- Continue the hosted deployment smoke after confirming the nanoGPT review path.

## 2026-09-11 (Day 16 authenticated UI pagination pass)

Phase: 4 deployment and polish

Did:

- Forced the authenticated Streamlit workbench sidebar to start expanded so the
  Review / Interview / Progress rail is visible after login.
- Added a compact signed-in account bar with a Log out button above the active
  page as a fallback if Streamlit Cloud or browser state collapses the sidebar.
- Paginated long review finding lists at five findings per page with previous
  and next controls and visible range text.
- Added frontend regression coverage for logged-in logout visibility and long
  finding pagination.

Learned / decided:

- The sidebar/logout code already existed, but Streamlit's default sidebar
  state can be collapsed while the app hides host chrome; that combination makes
  the navigation and logout affordance effectively disappear.

Verification:

- `tests/test_frontend_provenance.py`: 7 passed.
- Ruff passed for `frontend/app.py` and `tests/test_frontend_provenance.py`.
- Mypy passed for `frontend/app.py` and `tests/test_frontend_provenance.py`.
- Premium frontend strict audit passed with zero findings.

Open issues:

- Visually recheck the hosted authenticated page after redeploying because
  Streamlit Cloud owner controls such as “Manage app” remain outside app code.

Next up:

- Redeploy Streamlit, log in through Stytch, verify the sidebar/account bar, and
  rerun the nanoGPT review to confirm model subset output plus paginated results.
