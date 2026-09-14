# Frontend Memory

## Current state (2026-09-14, Next.js migration)

`frontend/` is now a Next.js 16 App Router project (Node 22, TypeScript,
strict mode) replacing Streamlit as the UI client. `frontend/app.py` and its
Streamlit tests/requirements remain in the tree only as a rollback artifact
per `UX-CONTRACT.md`; no new work should target them.

Screens:

- `/` — a static, pre-rendered marketing/landing page: hero with a worked
  example finding → interview follow-up, a three-step "how it works" section,
  and the email/local-practice login form (`components/login.tsx`).
- `/workspace` — the authenticated app shell (`components/workspace.tsx`,
  ~1,050 lines): Review (paste code or GitHub link, role selector, findings
  panel), Interview (question-by-question practice with scoring/feedback),
  and Progress (evidence-backed history, snapshot save). Client-rendered,
  session-gated.
- Server route handlers (not pages): `app/api/auth/[action]/route.ts`
  (login/local/callback/logout — Stytch magic link or, only when
  `CLUTCH_ALLOW_LOCAL_ANONYMOUS=true` and not on Vercel, an anonymous local
  session) and `app/api/clutch/[...path]/route.ts` (the sole allowlisted,
  origin-checked, ownership-signing proxy to FastAPI).

Wired up: full Review → Interview → feedback → Progress loop against a real
FastAPI backend, cross-user ownership isolation, CSRF/origin enforcement,
Stytch and local-anonymous auth, citation link sanitization, generic
user-facing error copy (no raw backend detail), pagination-free single-page
findings (all findings render; Streamlit's five-per-page limit was dropped
since the layout no longer needs it), and light/dark-agnostic (light-only)
premium visual design in `app/globals.css` (~1,600 lines, shared design
tokens with `DESIGN.md`).

Nothing is stubbed. No TODO/FIXME markers exist in `app/`, `components/`,
or `lib/`.

## Verification (2026-09-14)

- `npm run lint`, `npm run typecheck`, `npm test` (9 unit/contract/ownership
  tests, one integration test conditionally skipped), and `npm run build`
  all pass clean.
- `npm run test:integration` (`tests/run-integration.mjs`) spins up an
  isolated local FastAPI (`DATABASE_URL`/`REDIS_URL`/`OPENAI_API_KEY` forced
  empty — no production data or spend touched) and a production Next.js
  build on throwaway ports, then runs the full HTTP flow end to end:
  review → interview turns → feedback → progress, plus 401/403/404 ownership
  and CSRF checks. Passes.
- Manually verified the standalone Docker output
  (`CLUTCH_STANDALONE=true npm run build`, then `node .next/standalone
  /server.js` with `.next/static` copied alongside) serves `/`, `/workspace`,
  and `/icon.svg` with 200s — this is exactly what `frontend/Dockerfile`
  packages, confirming the multi-stage build is correct without needing a
  local Docker daemon (which was unavailable in this session, consistent
  with prior sessions' notes).
- Browser-verified with a headless-Chrome/Puppeteer driver (landing at
  1440px and 390px, workspace Review/Interview/Progress tabs, local-anonymous
  login, the generic "service unavailable" fallback banner with no backend
  running) — no horizontal overflow, no console errors after fixing the
  favicon 404 below.
- Added `app/icon.svg` (the brand mark, matching `components/brand.tsx`'s
  colors) so the browser's automatic `/favicon.ico` request no longer 404s;
  there was no `public/` directory or icon convention file before this.

## Decisions

- Session ownership: an HttpOnly/Secure(prod)/SameSite=Lax signed cookie
  (`lib/auth.ts`) carries either a Stytch-verified identity or, in local
  mode only, a locally-signed anonymous identity. The same `profileId()`
  hashing scheme as the legacy Streamlit app is reused so a user's progress
  history is continuous across the migration.
- `CLUTCH_ALLOW_LOCAL_ANONYMOUS` is read at module scope in `app/page.tsx`
  and is forced off whenever `process.env.VERCEL` is set, so anonymous
  practice can never accidentally ship to production.
- The proxy route (`app/api/clutch/[...path]/route.ts`) is the only place
  that holds `CLUTCH_API_KEY`; it allowlists product paths, rewrites/verifies
  profile IDs, checks request origin on mutations, and signs interview
  ownership into per-session cookies (bounded to the 11 most recent so
  header size can't grow unbounded).
- No client-side persistence: review/answer drafts live in React state only,
  matching the old Streamlit "no autosave" behavior; reloading loses the
  active draft, navigating stages within the workspace does not.
- Docker/Compose now expose the frontend on port 3000 (was 8501) and health-
  check with a plain `fetch()` instead of Streamlit's `_stcore/health`.
- CI gained a dedicated `frontend` job (lint, typecheck, unit tests, build,
  `npm audit --omit=dev`, then the Python-backed integration test) that other
  jobs (image builds) now depend on.

## Known gaps

- Hosted Vercel deployment itself has not happened yet; `docs/vercel-
  deployment.md` documents the Root Directory/env var/Stytch redirect setup
  and cutover checklist but nothing there has been exercised against a real
  Vercel project or a live Stytch project/domain.
- No visual regression/screenshot diffing is wired into CI; verification is
  manual (this session) or unit/contract-test-based.
- The 150s proxy timeout / 180s function duration assumption in
  `docs/vercel-deployment.md` has not been checked against the actual Vercel
  plan the user will deploy on.
