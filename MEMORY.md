# Project Memory

## Current State

The repo is in Phase 1 Day 3. It now has a runnable local pasted-code review
workflow with Python parsing and seed clean-code retrieval wired into the
backend.

Foundation docs:

- `AGENTS.md`: repo-wide Codex guidance and build phases.
- `PRD.md`: product requirements and v1 scope.
- `ARCHITECTURE.md`: full technical architecture and critique.
- `ARCHITECTURE_ESSENTIALS.md`: short daily architecture summary.
- `CLOUD.md`: AWS deployment and infrastructure plan.
- `PROGRESS.md`: dated session log.

Implementation:

- `pyproject.toml`: Python package metadata and dependencies.
- `src/clutch/schemas.py`: shared Pydantic contracts.
- `src/clutch/parsing/python.py`: tree-sitter Python parser producing
  line-aware chunks.
- `src/clutch/knowledge_base/clean_code.py`: seeded clean-code principles and
  deterministic lexical retrieval.
- `src/clutch/review/static.py`: deterministic Day 1 static reviewer.
- `backend/app/main.py`: FastAPI app with `/health` and `/review`.
- `frontend/app.py`: Streamlit pasted-code UI.
- `tests/test_python_parser.py`: parser unit tests.
- `tests/test_clean_code_retrieval.py`: seed retrieval tests.
- `tests/test_review_api.py`: route, validation, and parsed-metadata tests.

## Active Direction

The current implementation target remains the smallest runnable Phase 1 slice:

```text
Streamlit pasted Python code input
  -> FastAPI POST /review
  -> tree-sitter parsed chunks
  -> deterministic findings with retrieved seed citations
  -> validated CodeFinding[] response
  -> Streamlit findings display
```

Retrieval, LangGraph, GitHub MCP, evals, tracing, Redis, and cloud deployment
should be layered on only after this parsed review loop works well.

## Key Decisions

- Streamlit is the UI.
- FastAPI is the real backend boundary.
- The system uses one LangGraph agent unless evals justify more complexity.
- Pydantic schemas are required across API and LLM boundaries.
- Uploaded code is untrusted input and should not be persisted or logged beyond
  the current session.
- GitHub integration is read-only and belongs behind one MCP server.

## Known Gaps

- The static reviewer is intentionally shallow and deterministic.
- Tree-sitter parsing extracts functions/classes and falls back to a module
  chunk for non-definition snippets.
- Retrieval is a tiny seed corpus, not vector or hybrid search yet.
- No LangGraph graph or LLM provider path exists yet.
- Tracing provider and initial model choice are still open.
