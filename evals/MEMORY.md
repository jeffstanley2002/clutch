# Evals Memory

## Current state

- `fixtures/golden_reviews.json`: 12 typed Python cases: seven focused, three
  clean-negative, and two mixed-signal.
- `fixtures/github_reviews.json`: three multi-file repository cases run through
  `GitHubReviewService`: one focused, one clean-negative, and one mixed-signal.
- `fixtures/prompt_injection_cases.json`: three adversarial comment/string/
  README-style cases.
- `fixtures/interview_cases.json`: three complete weak/strong/mixed answer
  sequences with score, feedback, finding, and raw-answer privacy expectations.
- `src/clutch/evals/runner.py`: runs the real graph with `primary=None` and
  the real interview/report services, reporting review, retrieval, citation,
  coaching, guardrail, privacy, latency, and cost evidence.
- Dataset `2026-09-08.v5` passes every deterministic gate. Finding, citation,
  question, severity, clean-negative, mixed recall, interview, feedback,
  privacy, ingestion, and injection metrics are 1.0. Graded retrieval is
  Precision@3 0.786, Recall@3 0.559, nDCG@3 0.934, judgment coverage 1.0,
  and irrelevant-result rate 0.044; MRR is 1.0 and hallucinated-line rate is
  0.0.

## Decisions

- CI forces static fallback so it is deterministic, fast, secret-free, and
  zero-cost.
- Static execution reports model schema-validity as unmeasured.
- Perfect scores describe only named fixture coverage, never general quality.
- Expected findings are atomic objects so an ID from one finding cannot be
  incorrectly paired with the category or citation from another.
- Retrieval grades mean 0 irrelevant, 1 marginal context, 2 relevant, and 3
  highly relevant. Every current top-three candidate must be explicitly judged.
- Mixed repository queries can have more relevant items than K=3 can return;
  the Recall@3 floor is 0.55 while nDCG and irrelevant-rate gates protect order.

## Known gaps

- Compare lexical, vector-only, and hybrid retrieval on these same judgments.
- Live OpenAI accuracy, invalid-output, fallback, latency, token, and cost
  baselines require a user-provided key.
