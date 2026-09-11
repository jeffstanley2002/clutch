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

## 0. What You Will Create

You need accounts for GitHub, Render, Streamlit Community Cloud, Stytch,
OpenAI, Neon, and Langfuse. Redis is optional. The finished public path is:

1. Recruiter opens the Streamlit URL.
2. Stytch sends an email magic link and verifies the recruiter.
3. Streamlit calls Render with a server-side `CLUTCH_API_KEY`.
4. Render calls OpenAI and uses Neon for durable derived results.
5. Render sends privacy-reduced traces to Langfuse.

Before using either hosting dashboard, push the deployment commit to the GitHub
branch you intend to deploy. Streamlit Community Cloud runs from the repository
root and discovers the root `requirements.txt`; its entrypoint remains
`frontend/app.py`.

## 1. Rotate Secrets Before Deployment

Create fresh values before copying anything into a hosted provider:

- OpenAI API key.
- GitHub fine-grained token, if private-repository reads are required.
- Langfuse public/secret keys, or a fresh Langfuse project.
- A random `CLUTCH_API_KEY` shared only by Render and Streamlit.
- Neon database password/connection strings if they have been exposed anywhere.

Never commit these values. `.env`, `.env.local`, `.env.neon`, and `.neon` are
ignored, and `node_modules` is excluded from source control and Docker context.

Generate one random value locally:

```bash
openssl rand -hex 32  # CLUTCH_API_KEY
```

Do not paste the whole local `.env` into either provider. Use this map:

| Setting | Put it in | Required? | Where the value comes from |
|---|---|---:|---|
| `DATABASE_URL` | Render | Yes | Neon **pooled** production connection string (`-pooler` hostname) |
| `OPENAI_API_KEY` | Render | Yes for AI output | A newly rotated OpenAI project key |
| `CLUTCH_API_KEY` | Render + Streamlit | Yes | First random value above; both copies must match exactly |
| `LANGFUSE_PUBLIC_KEY` | Render | Recommended | Langfuse project settings |
| `LANGFUSE_SECRET_KEY` | Render | Recommended | Langfuse project settings |
| `LANGFUSE_BASE_URL` | Render | Yes when tracing | Region for that Langfuse project; the blueprint currently uses Japan Cloud |
| `GITHUB_TOKEN` | Render | Optional | Fine-grained read-only token; omit for public-repository-only demos |
| `REDIS_URL` | Render | Optional | Upstash/Redis Cloud URL; omit for the first single-instance deploy |
| `CLUTCH_API_BASE_URL` | Streamlit | Yes | Public Render URL after the backend is live |
| `stytch.project_id` | Streamlit | Yes | Stytch project dashboard |
| `stytch.secret` | Streamlit | Yes | Stytch project dashboard secret key |
| `stytch.environment` | Streamlit | Yes | `test` while using test keys; `live` after switching Stytch environments |
| `stytch.redirect_url` | Streamlit + Stytch | Yes | Exact Streamlit app URL, e.g. `https://<streamlit-app>.streamlit.app` |

`DIRECT_DATABASE_URL`, `CLUTCH_DB_*`, `LOCALSTACK_*`, and live-eval budget
variables are local/admin-only and do not belong in either hosted app. The
non-secret runtime defaults are already versioned in `render.yaml`.

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

Recommended path:

1. In Render, choose **New → Blueprint** and connect this GitHub repository.
2. Select the deployment branch and let Render read the root `render.yaml`.
3. Enter every value marked `sync: false` when Render prompts for it. Paste
   `REDIS_URL` too if you want shared cache/spend state from the first deploy;
   leave it empty only when deploying without Redis.
4. Confirm the free plan, then apply the Blueprint.
5. Wait for `/health` to pass and copy the service's
   `https://<clutch-api>.onrender.com` URL.

Render only prompts for `sync: false` variables when a Blueprint service is
first created. If the service already exists, add or rotate those values under
**Service → Environment** before redeploying.

If you create a Python Web Service manually instead, use:

- Name: `clutch-api`
- Runtime: Python
- Build command: `pip install -e .`
- Start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Set these Render secrets (`DATABASE_URL`, `OPENAI_API_KEY`, and
`CLUTCH_API_KEY` are the minimum model-backed deployment):

- `DATABASE_URL=<Neon pooled production URL>`
- `OPENAI_API_KEY=<rotated key>`
- `CLUTCH_API_KEY=<rotated random value>`
- `LANGFUSE_PUBLIC_KEY=<rotated key>`
- `LANGFUSE_SECRET_KEY=<rotated key>`
- `GITHUB_TOKEN=<rotated fine-grained token>` only if private repositories are
  part of the demo
- `REDIS_URL=<Redis Cloud URL>` for shared retrieval/spend caching

The blueprint supplies the non-secret defaults, including `gpt-5.4-mini`,
`text-embedding-3-small`, `CLUTCH_RETRIEVAL_STRATEGY=local_lexical`, API-key
enforcement, spend ceilings, in-process GitHub MCP, and redacted Langfuse IO.
Set `LANGFUSE_BASE_URL` to the region containing the rotated project.

Redis is optional for a single free Render instance, but the Blueprint now
prompts for `REDIS_URL` so Redis can be enabled during first deploy. Without
Redis, leave it empty; the same per-call and per-process daily model ceilings
still apply.

Free Render services can cold-start after idle periods, so allow the first
health request extra time.

## 4. Configure Stytch Magic Links

1. In Stytch, keep this project as **Consumer Auth**.
2. Use the **Backend only** implementation path.
3. Enable **Email Magic Links**.
4. Under **Redirect URLs**, add the exact Streamlit URL after choosing the
   Streamlit subdomain:

   `https://<streamlit-app>.streamlit.app`

Mark that URL as the default for Login and Signup. Keep the localhost redirect
only for local testing.

## 5. Deploy Streamlit Community Cloud

After Render is healthy, create the Streamlit app with:

- Repository: this GitHub repository
- Branch: the deployment branch
- Main file path: `frontend/app.py`
- Dependency file: root `requirements.txt`
- Python version: `3.11`

Open **Advanced settings** and paste this TOML into **Secrets**. Keep the two
`CLUTCH_*` keys above `[stytch]`; TOML keys written after `[stytch]` belong to that
table and the app will not find them as top-level settings.

```toml
CLUTCH_API_BASE_URL = "https://<clutch-api>.onrender.com"
CLUTCH_API_KEY = "<same rotated key configured on Render>"

[stytch]
project_id = "<stytch-project-id>"
secret = "<stytch-secret-key>"
environment = "test"
redirect_url = "https://<streamlit-app>.streamlit.app"
```

Streamlit uses Stytch email magic links for user login and sends only an opaque
hashed profile ID to FastAPI. It uses `CLUTCH_API_KEY` server-side when calling
FastAPI; the key is not rendered into the browser page. If you edit any Stytch
secret later, restart the Streamlit app so the configuration reloads.

## 6. Hosted Smoke and Manual Checks

Run the included smoke script after both services are live:

```bash
export CLUTCH_HOSTED_API_URL="https://<clutch-api>.onrender.com"
export CLUTCH_HOSTED_FRONTEND_URL="https://<streamlit-app>.streamlit.app"
export CLUTCH_API_KEY="<same rotated key>"
scripts/hosted_smoke.sh
```

Then verify in the UI:

- unauthenticated visitors see the Clutch landing/login screen;
- Stytch emails a magic link, redirects back to the Streamlit app, and shows a
  logout control;
- pasted-code and public-GitHub reviews complete;
- AI success and explicit fallback labels are accurate;
- an interview assessment and completed feedback report render;
- progress is tied to the signed-in Stytch identity and persists after a backend
  restart;
- the GitHub scope summary says it is not a full-codebase analysis; and
- Render, Neon, and Langfuse contain no raw source, raw answers, prompts,
  provider payloads, or secrets.

If magic links do not return to the app, compare the deployed Streamlit URL,
the `[stytch].redirect_url` value, and Stytch's Redirect URLs character for
character. If reviews return `401`, compare the Render and Streamlit copies
of `CLUTCH_API_KEY`. If the Streamlit page loads but review calls time out on the
first attempt, open the Render `/health` URL once and retry after the free
service wakes.

Langfuse's current Japan Cloud readback exposes model/version/token fields but
still omits native generation cost for the tested model trace. Keep that known
observability limitation visible until a fresh `scripts/audit_langfuse_trace.py`
run passes; do not present it as a complete native-cost audit.

## Official Provider References

- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Streamlit secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render free-service behavior](https://render.com/docs/free)
- [Stytch email magic links](https://stytch.com/docs/b2c/guides/magic-links/overview)
