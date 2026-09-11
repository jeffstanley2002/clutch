# Backend Memory

## Current state

`backend.app.main:app` is the thin FastAPI boundary. Routes are `GET /health`,
`GET /runtime/cache`, `GET /runtime/spend`, `POST /review`,
`POST /review/github`, `POST /interview/turn`,
`GET /interview/{session_id}/feedback`, `GET /progress/{profile_id}`, and
`POST /progress/{profile_id}/snapshots`.

Factories choose in-memory/local adapters unless database, Redis, model, MCP,
or tracing configuration is present. Model failures use typed labeled fallback
results; only combined model/fallback failures become privacy-safe errors.
GitHub MCP read failures are translated to clear 422 responses for the frontend,
including missing/private/token-inaccessible repo and PR cases.
Optional API-key middleware protects every non-health route and fails closed
when auth is required but unconfigured. Shutdown closes the shared database
engine, Redis/cache/spend clients, and Langfuse.

## Decisions

- Routes validate HTTP/Pydantic contracts and delegate; business logic stays in
  application services.
- Profile IDs are length/pattern constrained.
- `ReviewService` hashes source before recording derived metadata and attaches
  only safe inputs/outputs to the root trace.
- The backend container runs as UID/GID 10001 and does not auto-run migrations.

## Known gaps

- No streaming/SSE interview response yet.
- API-key auth is deployment-level; user accounts, key rotation, and request-rate
  limiting are not implemented.
- Render/Streamlit hosted smoke and restart-persistence evidence remain after
  deployment. Local and browser success/fallback/error paths are verified.
