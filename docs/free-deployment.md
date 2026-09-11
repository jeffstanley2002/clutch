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

You need accounts for GitHub, Render, Streamlit Community Cloud, Google Cloud,
OpenAI, Neon, and Langfuse. Redis is optional. The finished public path is:

1. Recruiter opens the Streamlit URL.
2. Google OIDC signs the recruiter in.
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

Generate two different random values locally:

```bash
openssl rand -hex 32  # CLUTCH_API_KEY
openssl rand -hex 32  # Streamlit auth.cookie_secret
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
| `auth.redirect_uri` | Streamlit + Google | Yes | Exact Streamlit URL ending in `/oauth2callback` |
| `auth.cookie_secret` | Streamlit | Yes | Second random value above |
| `auth.client_id` | Streamlit | Yes | Google OAuth web client |
| `auth.client_secret` | Streamlit | Yes | Google OAuth web client |
| `auth.server_metadata_url` | Streamlit | Yes | Google's shared OIDC discovery URL shown below |

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

## 4. Create the Google Login Client

1. In Google Auth Platform, configure **Branding** with the Clutch name and a
   support email.
2. Under **Audience**, choose External. While the app is in Testing, add your
   own Google account as a test user.
3. Under **Clients**, create a client with application type **Web application**.
4. Add this exact authorized redirect URI after choosing the Streamlit subdomain:

   `https://<streamlit-app>.streamlit.app/oauth2callback`

The scheme, hostname, path, and trailing slash must match exactly. For a
recruiter-facing link, do not leave the Google app restricted to your own test
user: move it to the appropriate production/published state after completing
Google's current consent-screen requirements.

## 5. Deploy Streamlit Community Cloud

After Render is healthy, create the Streamlit app with:

- Repository: this GitHub repository
- Branch: the deployment branch
- Main file path: `frontend/app.py`
- Dependency file: root `requirements.txt`
- Python version: `3.11`

Open **Advanced settings** and paste this TOML into **Secrets**. Keep the two
`CLUTCH_*` keys above `[auth]`; TOML keys written after `[auth]` belong to that
table and the app will not find them as top-level settings.

```toml
CLUTCH_API_BASE_URL = "https://<clutch-api>.onrender.com"
CLUTCH_API_KEY = "<same rotated key configured on Render>"

[auth]
redirect_uri = "https://<streamlit-app>.streamlit.app/oauth2callback"
cookie_secret = "<random-long-cookie-secret>"
client_id = "<google-oauth-client-id>"
client_secret = "<google-oauth-client-secret>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Streamlit uses Google OIDC for user login and sends only an opaque hashed
profile ID to FastAPI. It uses `CLUTCH_API_KEY` server-side when calling
FastAPI; the key is not rendered into the browser page. If you edit any auth
secret later, restart the Streamlit app so the OIDC configuration reloads.

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
- Google login redirects back to the Streamlit app and shows a logout control;
- pasted-code and public-GitHub reviews complete;
- AI success and explicit fallback labels are accurate;
- an interview assessment and completed feedback report render;
- progress is tied to the signed-in Google identity and persists after a backend
  restart;
- the GitHub scope summary says it is not a full-codebase analysis; and
- Render, Neon, and Langfuse contain no raw source, raw answers, prompts,
  provider payloads, or secrets.

If login returns `redirect_uri_mismatch`, compare the deployed Streamlit URL,
the `[auth].redirect_uri` value, and Google's authorized redirect URI character
for character. If reviews return `401`, compare the Render and Streamlit copies
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
- [Streamlit OIDC authentication](https://docs.streamlit.io/develop/concepts/connections/authentication)
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render free-service behavior](https://render.com/docs/free)
- [Google OAuth web-server setup](https://developers.google.com/identity/protocols/oauth2/web-server)
