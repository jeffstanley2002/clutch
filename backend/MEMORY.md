# Backend Memory

## Current state

`backend.app.main:app` is the thin FastAPI boundary. Routes are `GET /health`,
`GET /runtime/cache`, `GET /runtime/spend`, `POST /review`,
`POST /review/github`, `POST /interview/turn`,
`GET /interview/{session_id}/feedback`, `GET /progress/{profile_id}`, and
`POST /progress/{profile_id}/snapshots`.

Factories choose in-memory/local adapters unless database, Redis, model, MCP,
or tracing configuration is present. GitHub and interview errors become bounded
4xx/5xx responses without provider bodies. Optional API-key middleware protects
every non-health route and fails closed when auth is required but unconfigured.
Shutdown closes Redis/cache/spend clients and flushes Langfuse.

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
- Live OpenAI/Langfuse failure behavior needs credentialed staging evidence.
