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
