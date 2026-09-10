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
- Auth: when Streamlit OIDC `[auth]` secrets are configured, unauthenticated
  users see a recruiter-facing landing/login screen, Google handles sign-in,
  and the app derives a stable opaque `user_<sha256>` profile ID from the
  signed-in identity.

The full flow and a public GitHub review were browser-verified at desktop. The
model-backed and forced-fallback review states, rule-based interview assessment,
keyboard focus, answer clearing, citation deduplication, and empty/error states
were rechecked on 2026-09-10. The 390px layout has no horizontal overflow. Fresh
review, interview-assessment, and progress screenshots from the five-service
Compose stack live under `docs/images/` and are embedded in the README.
`DESIGN.md` passes the premium strict audit and official linter with zero
errors or warnings. Streamlit AppTest covers model/fallback origins, anchored
links, the exact GitHub scope message, the auth landing gate, and correct
top-level parsing of the hosted API settings in the Streamlit secrets example.

## Decisions

- The frontend only calls FastAPI through `CLUTCH_API_BASE_URL`; it never imports
  parser, provider, persistence, retrieval, or MCP business logic.
- It attaches the optional deployment API key server-side; that value is never
  rendered into browser state.
- `CLUTCH_API_BASE_URL` and `CLUTCH_API_KEY` can come from environment variables
  or `st.secrets`, so the same app runs locally and on Streamlit Community
  Cloud.
- Without Streamlit OIDC secrets, a local generated profile ID connects review,
  interview, and progress for anonymous development. With OIDC secrets, the
  hashed Google identity owns the profile ID.
- UI state covers initial, validation, loading, success, empty, and service
  failure behavior.
- The unauthenticated landing page is a hybrid marketing/product surface: it
  explains the project, shows the review-to-interview-to-progress flow, and
  names the concrete AI-engineering proof points before login.
- The landing hero uses a keyed native Streamlit container and columns. Raw HTML
  never spans the login widget, which keeps the workflow preview and login copy
  inside the same responsive card at desktop and 390px.
- Deployment placeholders and dummy OAuth test credentials use reviewed,
  line-local `detect-secrets` annotations; the repository does not suppress the
  keyword detector globally or weaken the committed baseline.
- Every finding, question, assessment, citation, and final aggregation has a
  literal origin label. A warning appears whenever the applicable model did not
  complete; deterministic/template output is never described as AI-generated.

## Known gaps

- No user-account picker, historical snapshot list, report export format, or
  backend-side JWT verification; Streamlit owns user login for the v1 demo.
- SSE/live token streaming is deferred until interview behavior is richer.
