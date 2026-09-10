# Interview Memory

## Current state

`InterviewService` starts from typed generated questions, retrieves up to three
category/citation-grounded corpus items, and prefers the structured
`interview_assessment.v1` model call. It returns score, strengths, gaps,
feedback, citations, provenance, next question, turn number, and completion
state. Provider/validation failure returns an explicitly labeled rule-based
assessment. Completed sessions produce a typed deterministic `FeedbackReport`
whose aggregation label identifies whether turns were AI- or rule-assessed.

Raw answers never persist; each turn stores answer SHA-256 and a bounded signal
summary. The current question/remaining generated questions are durable.

## Decisions

- Keep each answer request-scoped and send it only to the selected model with
  `store=False`; persistence/tracing receive its hash and bounded signals.
- Unknown sessions are a typed repository error mapped to HTTP 404.

## Known gaps

- SSE token streaming and adaptive questions between turns remain deferred.
- The live baseline achieved 0.833 score-within-one agreement but only 0.333
  exact-score agreement; do not overstate readiness accuracy.
