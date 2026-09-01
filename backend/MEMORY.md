# Backend Memory

## Current State

The backend exposes a small FastAPI app at `backend.app.main:app`.

Routes:

- `GET /health`: returns `{"status": "ok"}`.
- `POST /review`: accepts `ReviewRequest` and returns `list[CodeFinding]`.

## Decisions

- The first `/review` route is deterministic and local-only. It calls
  `run_static_review` rather than an LLM so the API contract can be tested
  before retrieval, LangGraph, and model calls are introduced.
- Raw pasted code is only used in-memory for the request and is not logged or
  persisted.

## Known Gaps

- No parser yet.
- No retrieval citations beyond seed static-review citations.
- No LangGraph agent orchestration yet.

