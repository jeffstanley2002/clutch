# Frontend Memory

## Current State

The Streamlit app in `frontend/app.py` supports the first pasted-code review
workflow. It collects role context and Python code, calls FastAPI
`POST /review`, and renders structured findings.

## Decisions

- The UI reads `CLUTCH_API_BASE_URL`, defaulting to `http://localhost:8000`.
- The frontend stays thin: it does not call model providers, retrieval, or
  parsers directly.

## Known Gaps

- No interview or progress screens yet.
