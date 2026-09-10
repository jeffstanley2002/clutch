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
- `src/clutch/evals/retrieval_comparison.py`: evaluates local lexical,
  PostgreSQL lexical, PostgreSQL vector-only, and PostgreSQL hybrid strategies
  over the same 15 privacy-bounded queries and judgments. Reports contain only
  query hashes, categories, retrieved source IDs, metrics, latency, and cost.
- `src/clutch/evals/live_model.py`: manually runs six representative review
  cases and all three injection cases through the production graph. It has an
  isolated $0.50 default cap, reports model/fallback/validation/quality/latency/
  token/cost metrics, and never serializes fixture source or prompts.
- Dataset `2026-09-10.v6` passes every deterministic gate. Finding, citation,
  question, severity, clean-negative, mixed recall, interview, feedback,
  privacy, ingestion, and injection metrics are 1.0. Graded retrieval is
  Precision@3 0.800, Recall@3 0.563, nDCG@3 0.970, judgment coverage 1.0,
  and irrelevant-result rate 0.000; MRR is 1.0 and hallucinated-line rate is
  0.0.

## Decisions

- CI uses the explicitly labeled deterministic paths so it is fast,
  secret-free, and zero-cost.
- Live evaluation is manual and fails closed: no key returns typed unavailable
  output without a client call; any configured fallback returns nonzero.
- Static execution reports model schema-validity as unmeasured.
- Perfect scores describe only named fixture coverage, never general quality.
- Expected findings are atomic objects so an ID from one finding cannot be
  incorrectly paired with the category or citation from another.
- Retrieval grades mean 0 irrelevant, 1 marginal context, 2 relevant, and 3
  highly relevant. Every current top-three candidate must be explicitly judged.
- Mixed repository queries can have more relevant items than K=3 can return;
  the Recall@3 floor is 0.55 while nDCG and irrelevant-rate gates protect order.
- Candidate strategies may have up to 10% unjudged top-three results. Unjudged
  hits are still relevance zero for nDCG and irrelevant-rate, avoiding a hidden
  quality exemption while preventing an exact-coverage double penalty.
- Neon comparison baseline: local lexical passes and wins at nDCG@3 0.970;
  Neon lexical/vector/hybrid remain below one or more unchanged gates. The full
  privacy-safe evidence is `baselines/retrieval-neon-production.json`.
- Credentialed `gpt-5.4-mini` baseline passes: finding/citation/question/
  injection/privacy metrics are 1.0, interview within-one is 0.833, schema
  failures are zero, and total cost is $0.028781.

## Known gaps

- Improve Neon hybrid retrieval without weakening gates, then rerun the same
  benchmark before changing `CLUTCH_RETRIEVAL_STRATEGY`.
- Add broader human labels before treating either live baseline as general
  quality evidence.
