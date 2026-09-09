# Frontend Memory

## Current state

The Streamlit app implements a three-stage workflow rail:

- Review: pasted Python or GitHub repo/PR + optional ref, role context, findings,
  citations, source/MCP summary, and generated questions.
- Interview: starts from generated questions, validates blank answers, renders
  per-turn score/signals/feedback, advances until complete, then renders the
  structured readiness summary, strengths, recurring issues, practice tasks,
  and privacy-safe supporting findings.
- Progress: shows improved/persistent categories, evidence session IDs, practice
  tasks, and can save a snapshot.

The full flow and a public GitHub review were browser-verified at desktop. The
new final report was rechecked at 390px without horizontal overflow. Fresh
review, interview-assessment, and progress screenshots from the five-service
Compose stack live under `docs/images/` and are embedded in the README.
`DESIGN.md` passes its strict audit/linter.

## Decisions

- The frontend only calls FastAPI through `CLUTCH_API_BASE_URL`; it never imports
  parser, provider, persistence, retrieval, or MCP business logic.
- It attaches the optional deployment API key server-side; that value is never
  rendered into browser state.
- A local generated profile ID connects review, interview, and progress without
  introducing premature account/auth state.
- UI state covers initial, validation, loading, success, empty, and service
  failure behavior.

## Known gaps

- No user-account picker, historical snapshot list, or report export format.
- SSE/live token streaming is deferred until interview behavior is richer.
