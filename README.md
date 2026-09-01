# Clutch

Clutch is a read-only AI code review and interview prep partner for junior
engineers. The Day 1 slice is a local pasted-code review loop:

```text
Streamlit UI -> FastAPI POST /review -> Pydantic CodeFinding[]
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

The first reviewer is deterministic and intentionally local-only. Tree-sitter,
retrieval, LangGraph, and model-backed structured review are layered in after
this contract is stable.

