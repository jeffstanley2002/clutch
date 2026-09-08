# Evals Memory

## Current state

- `fixtures/golden_reviews.json`: 12 typed Python cases: seven focused, three
  clean-negative, and two mixed-signal.
- `fixtures/prompt_injection_cases.json`: three adversarial comment/string/
  README-style cases.
- `fixtures/interview_cases.json`: three complete weak/strong/mixed answer
  sequences with score, feedback, finding, and raw-answer privacy expectations.
- `src/clutch/evals/runner.py`: runs the real graph with `primary=None` and
  the real interview/report services, reporting review, retrieval, citation,
  coaching, guardrail, privacy, latency, and cost evidence.
- Dataset `2026-09-08.v3` passes every deterministic gate. Finding, citation,
  question, severity, clean-negative, mixed recall, interview, feedback,
  privacy, and injection metrics are 1.0. Graded retrieval is Precision@3
  0.727, Recall@3 0.649, nDCG@3 0.951, judgment coverage 1.0, and
  irrelevant-result rate 0.028; hallucinated-line rate is 0.0.

## Decisions

- CI forces static fallback so it is deterministic, fast, secret-free, and
  zero-cost.
- Static execution reports model schema-validity as unmeasured.
- Perfect scores describe only named fixture coverage, never general quality.
- Expected findings are atomic objects so an ID from one finding cannot be
  incorrectly paired with the category or citation from another.
- Retrieval grades mean 0 irrelevant, 1 marginal context, 2 relevant, and 3
  highly relevant. Every current top-three candidate must be explicitly judged.

## Known gaps

- Add multi-file repository cases and extend judgments as the corpus grows.
- Live OpenAI accuracy, invalid-output, fallback, latency, token, and cost
  baselines require a user-provided key.
