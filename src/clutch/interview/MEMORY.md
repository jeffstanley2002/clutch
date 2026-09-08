# Interview Memory

## Current state

`InterviewService` starts from typed generated questions, records a multi-turn
session, deterministically assesses answers, and returns score, observed
signals, feedback, next question, turn number, and completion state. Completed
sessions produce a typed `FeedbackReport` with ranked strengths, repeated gaps,
practice tasks, a bounded readiness summary, and privacy-safe supporting review
findings. In-memory and SQLAlchemy repositories share the same contract.

Raw answers never persist; each turn stores answer SHA-256 and a bounded signal
summary. The current question/remaining generated questions are durable.

## Decisions

- Start with explainable deterministic assessment before introducing another
  model call.
- Unknown sessions are a typed repository error mapped to HTTP 404.

## Known gaps

- Generate adaptive follow-ups only after eval evidence justifies another model
  call.
- Add interview-answer golden labels and model/judge evaluation before claiming
  readiness accuracy.
