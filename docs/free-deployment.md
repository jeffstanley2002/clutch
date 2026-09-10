# Neon → Render → Streamlit Deployment Runbook

Clutch's production data layer is already prepared. The only remaining work is
to deploy the FastAPI service to Render and the UI to Streamlit Community Cloud,
then supply rotated secrets in those providers.

```text
Neon production Postgres + pgvector
                |
Render FastAPI + one LangGraph agent
                |
Streamlit Community Cloud UI
```

AWS Terraform remains unapplied architecture evidence. Do not apply it unless
the separate budget checkpoint in `CLOUD.md` is reopened.

## 1. Rotate Secrets Before Deployment

Create fresh values before copying anything into a hosted provider:

- OpenAI API key.
- GitHub fine-grained token, if private-repository reads are required.
- Langfuse public/secret keys, or a fresh Langfuse project.
- A random `CLUTCH_API_KEY` shared only by Render and Streamlit.
- Neon database password/connection strings if they have been exposed anywhere.

Never commit these values. `.env`, `.env.local`, `.env.neon`, and `.neon` are
ignored, and `node_modules` is excluded from source control and Docker context.

## 2. Neon Is Ready

Project `holy-feather-79203801`, branch `production`, is linked locally. On
2026-09-10 it was prepared and verified with:

- named pre-migration snapshot `clutch-pre-migration-20260910`;
- Alembic head `20260909_0003`;
- all ten required application tables;
- exactly 120 active versioned corpus rows;
- exact source provenance on all 120 rows;
- 1536-dimensional `text-embedding-3-small` vectors on all 120 rows;
- no raw-code or raw-answer columns; and
- a successful temporary read/write through the pooled production URL.

Use the pooled connection string for Render application traffic. Its hostname
contains `-pooler`. Paste the normal `postgresql://...` URL into Render as
`DATABASE_URL`; Clutch converts it to SQLAlchemy's async form in memory.

Use the direct, non-`-pooler` URL only for Alembic and administrative seeding.
For a future migration from a trusted shell:

```bash
CLUTCH_NEON_DIRECT_URL="$(neon connection-string production --database-name neondb)"
DIRECT_DATABASE_URL="$CLUTCH_NEON_DIRECT_URL" .venv/bin/alembic upgrade head
```

`neon deploy` applies `neon.ts`; Alembic remains the application schema source
of truth. The included HTTPS helpers are for environments that block port 5432:

```bash
DIRECT_DATABASE_URL="...direct URL..." node scripts/verify_neon_database.mjs --require-seeded
DATABASE_URL="...pooled URL..." node scripts/verify_neon_database.mjs --runtime --require-seeded
```

The production retrieval comparison selected `local_lexical` as the only
strategy meeting every current gate. Neon lexical, vector, and hybrid remain
available for future measured improvements; do not set one as the default until
a new baseline passes unchanged thresholds.

## 3. Deploy the Render Backend

Create a Render Blueprint from this repository's `render.yaml`, or create one
Python Web Service manually with these settings:

- Name: `clutch-api`
- Runtime: Python
- Build command: `pip install -e .`
- Start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Set these Render secrets:

- `DATABASE_URL=<Neon pooled production URL>`
- `OPENAI_API_KEY=<rotated key>`
- `LANGFUSE_PUBLIC_KEY=<rotated key>`
- `LANGFUSE_SECRET_KEY=<rotated key>`
- `CLUTCH_API_KEY=<rotated random value>`
- `GITHUB_TOKEN=<rotated fine-grained token>` only if private repositories are
  part of the demo

The blueprint supplies the non-secret defaults, including `gpt-5.4-mini`,
`text-embedding-3-small`, `CLUTCH_RETRIEVAL_STRATEGY=local_lexical`, API-key
enforcement, spend ceilings, in-process GitHub MCP, and redacted Langfuse IO.
Set `LANGFUSE_BASE_URL` to the region containing the rotated project.

Redis is optional for a single free Render instance. Add `REDIS_URL` later only
if shared cache/spend counters across replicas are needed. Without Redis, the
same per-call and per-process daily model ceilings still apply.

Free Render services can cold-start after idle periods, so allow the first
health request extra time.

## 4. Deploy Streamlit Community Cloud

After Render is healthy, create the Streamlit app with:

- Repository: this GitHub repository
- Branch: the deployment branch
- Main file path: `frontend/app.py`
- Dependency file: root `requirements.txt`

Add this TOML in Streamlit Advanced settings:

```toml
CLUTCH_API_BASE_URL = "https://<clutch-api>.onrender.com"
CLUTCH_API_KEY = "<same rotated key configured on Render>"
```

Streamlit uses the key server-side when calling FastAPI; it is not rendered into
the browser page.

## 5. Hosted Smoke and Manual Checks

Run the included smoke script after both services are live:

```bash
export CLUTCH_HOSTED_API_URL="https://<clutch-api>.onrender.com"
export CLUTCH_HOSTED_FRONTEND_URL="https://<streamlit-app>.streamlit.app"
export CLUTCH_API_KEY="<same rotated key>"
scripts/hosted_smoke.sh
```

Then verify in the UI:

- pasted-code and public-GitHub reviews complete;
- AI success and explicit fallback labels are accurate;
- an interview assessment and completed feedback report render;
- progress persists after a backend restart;
- the GitHub scope summary says it is not a full-codebase analysis; and
- Render, Neon, and Langfuse contain no raw source, raw answers, prompts,
  provider payloads, or secrets.

Langfuse's current Japan Cloud readback exposes model/version/token fields but
still omits native generation cost for the tested model trace. Keep that known
observability limitation visible until a fresh `scripts/audit_langfuse_trace.py`
run passes; do not present it as a complete native-cost audit.
