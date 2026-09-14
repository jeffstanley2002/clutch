# Deploy the Next.js frontend to Vercel

Clutch now uses `frontend/` as a Next.js App Router project. The public landing
page and workspace shell are pre-rendered; FastAPI stays on Render. The old
`frontend/app.py` is retained only as a rollback client during migration.

## Local development

1. Run FastAPI as before: `.venv/bin/uvicorn backend.app.main:app --reload`.
2. Copy `frontend/.env.example` to `frontend/.env.local`.
3. For anonymous local practice only, set `CLUTCH_ALLOW_LOCAL_ANONYMOUS=true`.
4. Run `npm ci --prefix frontend` and `npm run dev --prefix frontend`.
5. Open http://localhost:3000 and choose **Open local practice workspace**.

No paid model is required. Omit backend provider credentials for a labeled
static/template/rule-based smoke test. Docker Compose also uses Next.js on 3000.

## Vercel settings

Import the Git repository, select **Next.js**, and set **Root Directory** to
`frontend`. Use Node.js **22.x**, `npm ci`, `npm run build`, and the default
Next.js output setting (do not set it to `out`). No `vercel.json` is necessary.

Set these server-only environment variables in Vercel, then redeploy:

| Variable | Value / purpose |
|---|---|
| `CLUTCH_API_BASE_URL` | The HTTPS Render backend origin, without a path |
| `CLUTCH_API_KEY` | Same deployment API key configured on FastAPI |
| `CLUTCH_SESSION_SECRET` | A new random secret of at least 32 characters; signs session ownership |
| `STYTCH_PROJECT_ID` | Existing Stytch consumer project ID |
| `STYTCH_SECRET` | Existing Stytch consumer API secret |
| `STYTCH_ENVIRONMENT` | `test` or `live`, matching the project |
| `STYTCH_REDIRECT_URL` | `https://YOUR-DOMAIN/api/auth/callback` |

Never use `NEXT_PUBLIC_` for any of these values. Provider keys, database URLs,
Redis, and Langfuse credentials remain on FastAPI, not Vercel. Anonymous mode
is disabled on Vercel even if the local flag is accidentally set. Missing auth
configuration fails closed; the landing page still renders without credentials.

Add the callback URL to **both login and signup redirects** in the Stytch
project. Configure preview environments separately or keep preview auth
unconfigured; do not point a preview's callback at production accidentally.
The callback exchanges the one-use token, stores an HttpOnly/Secure/SameSite
session cookie, and redirects to `/workspace` without the token in the URL.
The frontend verifies Stytch sessions before proxying requests and uses the
same hashed Stytch user ID as the legacy app, preserving progress ownership.
The proxy constrains routes, overwrites client-supplied profile IDs, verifies
signed review/interview ownership, and never returns deployment credentials.

## Cutover verification

- Load `/` from a fresh browser and check the page appears before sign-in or
  backend requests. Measure hosted cold/warm visits; no timing claim is made yet.
- Request a login link, follow it, and verify Review → Interview → report → Progress.
- Confirm fallback origins, source citations, invalid GitHub inputs, backend
  failure/retry, and mobile rendering at 390px.
- Verify unauthenticated API requests return 401 and unsupported proxy paths 404.
- Complete two reviews with the same signed-in user and verify progress continuity.
- Keep FastAPI's API key required and its existing model-spend ceilings enabled.
- After the Vercel smoke passes, retire the old Streamlit deployment and disable
  its scheduled keepalive workflow. It remains in the repo for rollback meanwhile.

Vercel only removes the Streamlit-hosted startup surface. Render cold starts,
model latency, and Stytch availability still affect their respective operations.
The proxy has a 150-second upstream timeout and requests a 180-second function
budget; confirm that the chosen Vercel plan supports that duration. A timed-out
interview write may already have completed: automatic mutation retries are off.
Source and answer drafts live in React memory, not persistent browser storage;
reloading loses the active review/interview view (progress remains on FastAPI).
The legacy AWS frontend Terraform still describes Streamlit and is not the
Vercel deployment path; migrate it explicitly before any future AWS apply.

References: [Next.js route handlers](https://nextjs.org/docs/app/api-reference/file-conventions/route),
[Stytch magic links](https://stytch.com/docs/api-reference/consumer/api/magic-links/authenticate),
[Stytch redirects](https://stytch.com/docs/resources/workspace-management/redirect-urls).
