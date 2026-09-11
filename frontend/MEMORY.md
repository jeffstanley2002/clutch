# Frontend Memory

## Current state

The Streamlit app implements a three-stage workflow rail:

- Review: pasted Python or GitHub repo/PR + optional ref, role context, findings,
  anchored citations, bounded source/MCP summary, generated questions, and a
  stage-level provenance disclosure with model/version/tokens/latency/cost.
- Interview: starts from generated questions, validates blank answers, renders
  per-turn score/signals/feedback, advances until complete, then renders the
  structured readiness summary, strengths, recurring issues, practice tasks,
  and privacy-safe supporting findings.
- Progress: shows improved/persistent categories, evidence session IDs, practice
  tasks, and can save a snapshot.
- Auth: when Stytch `[stytch]` secrets are configured, unauthenticated users see
  a recruiter-facing landing/login screen, Stytch sends email magic links, and
  the app derives a stable opaque `user_<sha256>` profile ID from the signed-in
  identity.

The full flow and a public GitHub review were browser-verified at desktop. The
model-backed and forced-fallback review states, rule-based interview assessment,
keyboard focus, answer clearing, citation deduplication, and empty/error states
were rechecked on 2026-09-10. The 390px layout has no horizontal overflow. Fresh
review, interview-assessment, and progress screenshots from the five-service
Compose stack live under `docs/images/` and are embedded in the README.
`DESIGN.md` passes the premium strict audit and official linter with zero
errors or warnings. Streamlit AppTest covers model/fallback origins, anchored
links, the exact GitHub scope message, the auth landing gate, correct top-level
parsing of the hosted API settings in the Streamlit secrets example, and a
guard that prevents `pandas` from being imported during initial app startup.

## Decisions

- The frontend only calls FastAPI through `CLUTCH_API_BASE_URL`; it never imports
  parser, provider, persistence, retrieval, or MCP business logic.
- It attaches the optional deployment API key server-side; that value is never
  rendered into browser state.
- `CLUTCH_API_BASE_URL` and `CLUTCH_API_KEY` can come from environment variables
  or `st.secrets`, so the same app runs locally and on Streamlit Community
  Cloud.
- Without Stytch secrets, a local generated profile ID connects review,
  interview, and progress for anonymous development. With Stytch secrets, the
  hashed Stytch user identity owns the profile ID.
- UI state covers initial, validation, loading, success, empty, and service
  failure behavior.
- The unauthenticated landing page is a public product surface: it explains the
  project, shows a compact review-to-interview loop preview, and names the main
  user-facing strengths before login: cited findings, GitHub review, interview
  follow-ups, progress history, and private practice sessions. Keep recruiter
  and demo-specific language off the page; avoid exposing internal schema-chain
  shorthand or raw-retention slogans in the hero.
- The landing hero uses a keyed native Streamlit container and columns. Raw HTML
  never spans the login widget, which keeps the workflow preview and login copy
  inside the same responsive card at desktop and 390px. The Stytch form has an
  explicit hero-local margin/padding treatment so the magic-link box does not
  sit tightly against the capability chips.
- `.streamlit/config.toml` sets `[client].toolbarMode = "viewer"` and the app
  stylesheet hides reachable Streamlit toolbar/menu chrome. Streamlit Community
  Cloud can still show owner/deployment controls such as “Manage app” to signed
  in owners outside the app DOM.
- Deployment placeholders use reviewed, line-local `detect-secrets`
  annotations; the repository does not suppress the keyword detector globally or
  weaken the committed baseline.
- Every finding, question, assessment, citation, and final aggregation has a
  literal origin label. A warning appears whenever the applicable model did not
  complete; deterministic/template output is never described as AI-generated.

## Known gaps

- No user-account picker, historical snapshot list, report export format, or
  backend-side JWT verification; Streamlit owns user login for the v1 demo.
- SSE/live token streaming is deferred until interview behavior is richer.
- Streamlit Community Cloud can still show its host-owned dark skeleton while a
  sleeping app wakes or starts. The app can reduce this window, but cannot fully
  replace that wrapper screen from inside Streamlit code.
