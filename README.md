# Clutch

Clutch is a read-only AI code review and interview prep partner for junior
engineers. The current Phase 1 slice is a local pasted-code review loop with
Python parsing wired into the backend:

```text
Streamlit UI -> FastAPI POST /review -> tree-sitter Python parsing -> Pydantic CodeFinding[]
```

## Local Development

Install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the backend:

```bash
uvicorn backend.app.main:app --reload
```

Run the Streamlit UI:

```bash
streamlit run frontend/app.py
```

Run tests:

```bash
python -m pytest
```

The first reviewer is deterministic and intentionally local-only. It now uses
tree-sitter metadata for line-aware review context. Retrieval, LangGraph, and
model-backed structured review are layered in after this contract is stable.
