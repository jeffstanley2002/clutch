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

The full flow and a public GitHub review were browser-verified at desktop. The
model-backed and forced-fallback review states, rule-based interview assessment,
keyboard focus, answer clearing, citation deduplication, and empty/error states
were rechecked on 2026-09-10. The 390px layout has no horizontal overflow. Fresh
review, interview-assessment, and progress screenshots from the five-service
Compose stack live under `docs/images/` and are embedded in the README.
`DESIGN.md` passes the premium strict audit and official linter with zero
errors or warnings. Streamlit AppTest covers model/fallback origins, anchored
links, and the exact GitHub scope message.

## Decisions

- The frontend only calls FastAPI through `CLUTCH_API_BASE_URL`; it never imports
  parser, provider, persistence, retrieval, or MCP business logic.
- It attaches the optional deployment API key server-side; that value is never
  rendered into browser state.
- `CLUTCH_API_BASE_URL` and `CLUTCH_API_KEY` can come from environment variables
  or `st.secrets`, so the same app runs locally and on Streamlit Community
  Cloud.
- A local generated profile ID connects review, interview, and progress without
  introducing premature account/auth state.
- UI state covers initial, validation, loading, success, empty, and service
  failure behavior.
- Every finding, question, assessment, citation, and final aggregation has a
  literal origin label. A warning appears whenever the applicable model did not
  complete; deterministic/template output is never described as AI-generated.

## Known gaps

- No user-account picker, historical snapshot list, or report export format.
- SSE/live token streaming is deferred until interview behavior is richer.
