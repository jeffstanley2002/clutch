# Backend Memory

## Current State

The backend exposes a small FastAPI app at `backend.app.main:app`.

Routes:

- `GET /health`: returns `{"status": "ok"}`.
- `POST /review`: accepts `ReviewRequest` and returns `list[CodeFinding]`.
  The route parses pasted Python with tree-sitter before calling the
  deterministic reviewer, whose citations now come from seed clean-code
  retrieval.

## Decisions

- The first `/review` route is deterministic and local-only. It calls
  `parse_python_code` and then `run_static_review` rather than an LLM so the
  API contract can be tested before retrieval, LangGraph, and model calls are
  introduced.
- Raw pasted code is only used in-memory for the request and is not logged or
  persisted.
- The API response shape remains `list[CodeFinding]`; retrieval is an internal
  grounding step for now.

## Known Gaps

- Parser metadata is not exposed directly in the API yet; it only improves the
  internal review context.
- Citations are grounded in a small seed knowledge base, but there is no
  database/vector retrieval yet.
- No LangGraph agent orchestration yet.
