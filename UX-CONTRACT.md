# Clutch UI contract

The visual system is `DESIGN.md`. Product scope: `PRD.md`. API field shapes:
`src/clutch/schemas.py`; lifecycle: `src/clutch/interview/service.py`.
Authentication/proxy ownership: `frontend/lib/auth.ts` and API route handlers.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Native role select in workspace | DESIGN.md | native OS popup | browser keyboard and opened popup |
| Form | Shared CSS labels/inputs and schema contracts | schemas.py, contracts.ts | review, answer, login | inline validation + API tests |
| Scrollbar | app/globals.css | DESIGN.md | normal / forced colors | root computed style and browser |
| Toast | Workspace feedback-region and login-status | workspace.tsx, login.tsx | success / busy / error | browser pending/error/success |
| Navigation | Workspace stage buttons | workspace.tsx | Review / Interview / Progress | drafts preserved during switching |
| Provenance | components/ui.tsx | schemas.py | stage, citation, origin | schema tests and browser fallback |

## Workflow ledger

- Review submit locks controls, sends a bounded request, and replaces review /
  questions only on success. The prior result remains after failure. Five
  findings per page; paging stays in memory because results are session-private.
- Interview begins with at most five questions from an owned review. Answer
  submission is single-flight. Advance and clear the answer only on success.
  Completed interview exposes a retryable report load; report never restarts it.
- Progress loads on entering the stage; Refresh retries explicitly. Save reports
  success without changing navigation. Use evidence session IDs for grounding.
- Source and answer text are transient in-memory drafts. Stage navigation keeps
  them. Real unload uses beforeunload; home opens in a separate tab to preserve
  the workspace. Explicit logout clears the workspace. There is no autosave.
- No automatic retry for writes: a timeout can mean the operation completed.
  Existing backend has no idempotency/recovery endpoint; state this in errors.
- Provider/source strings are untrusted text. Citation href permits HTTP(S) only.
- Production identity comes from verified Stytch session cookies, never browser
  profile fields. The proxy overwrites profile IDs, limits paths, checks origin
  for writes, and requires signed session ownership for interview operations.
  Backend-wide API key remains required; no account-deletion/billing UI added.
- Locale is English. Numbers use en formatting. Read-only workflow has no date
  picker, table selection, bulk actions, destructive CRUD, or upload UI.

## Migration / rollback

Next.js owns the current frontend, Compose image, and Vercel instructions.
`frontend/app.py`, legacy tests, and Streamlit keepalive remain rollback
artifacts until hosted Vercel smoke verification. AWS Terraform still describes
its historical frontend and must not be applied as if it were the Vercel path.

## Evidence

Unit/contract/ownership tests: `frontend/tests/`. HTTP integration runs against
an isolated local FastAPI and Next.js process with `CLUTCH_TEST_URL` set.
Browser verification and remaining limits: `frontend/MEMORY.md` and PROGRESS.md.
