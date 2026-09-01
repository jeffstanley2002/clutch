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
