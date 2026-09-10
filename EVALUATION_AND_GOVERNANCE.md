# Evaluation and Governance

Clutch uses eval evidence to decide whether AI behavior is ready to ship and
whether added complexity earns its place.

## Golden Dataset

The current dataset contains 15 Python review samples: 12 pasted-code cases and
three multi-file repository cases evaluated through the real GitHub review
coordinator. Across both sources there are eight focused positives, four clean
negatives, and three mixed-signal cases. Separate adversarial
fixtures place prompt-injection instructions in comments, strings, and
README-style text. Three interview fixtures run complete weak, strong, and mixed
answer sequences through final feedback generation.

Review cases store atomic expected findings—ID prefix, category, severity, and
required citations—plus question keywords and 0–3 retrieval relevance judgments
(irrelevant, marginal, relevant, highly relevant). Interview cases store exact score,
strength, recurring-gap, task, readiness, supporting-finding, and raw-answer
privacy expectations. Injection cases record prohibited output terms. Dataset
changes are reviewed like code because changing labels can hide regressions.

## Metrics

- Retrieval: Recall@K, Precision@K, MRR, nDCG@K, judgment coverage, and
  irrelevant-result rate.
- Findings: precision, recall, severity calibration, and hallucinated-line rate.
- Questions: relevance to findings and role context.
- Grounding: citation validity and deterministic concept-level citation support.
- Reliability: schema-valid response rate, retry rate, and fallback rate.
- Guardrails: prompt-injection pass rate and prohibited-tool-call count.
- System: end-to-end/node latency, tokens, estimated cost, and cache hit rate.

## Gates

- Deterministic unit and API tests must pass on every change.
- The compact golden and injection suites gate every pull request and main push.
- Prompt-injection pass rate is 100% for the committed adversarial suite.
- Citation validity must be 100%, citation support at least 90%, hallucinated
  line rate 0%, finding precision at least 75%, finding recall at least 70%,
  question relevance at least 80%, interview score-within-one at least 80%, and
  prompt-injection pass rate 100%.
- Retrieval strategies must meet Recall@3 >= 0.55, MRR 1.0, nDCG@3 >= 0.90,
  judgment coverage@3 >= 0.90, and irrelevant-result rate@3 <= 0.15.
- Full and potentially costly model evals run manually or on a controlled
  schedule; CI uses deterministic/frozen paths.

`python -m clutch.evals.live_model --compact` is the controlled live gate. It
uses six representative review cases plus all three injection cases, a separate
in-memory spend guard capped at $0.50 by default, and the production graph with
local retrieval. The privacy-reduced report contains IDs, metrics, safe failure
categories, tokens, latency, and charged cost—never fixture source or prompts.
Missing credentials return a typed unavailable result without a provider call;
any fallback causes a nonzero configured-run exit.

Prompt text is governed by a version/hash manifest. CI fails when prompt content
changes without a version bump and refreshed manifest/baseline evidence.

## Current Baseline

Dataset version `2026-09-10.v6` runs the real review graph through its labeled
deterministic paths, then runs the actual interview service and final-report
generator against in-memory privacy-safe repositories. The three
GitHub cases verify selected-file metadata and prove that request-scoped source
sentinels do not enter persisted review records. It also contains three
prompt-injection cases and three complete interviews.

| Metric | Baseline |
|---|---:|
| Finding precision | 1.000 |
| Finding recall | 1.000 |
| Finding severity accuracy | 1.000 |
| Clean-negative pass rate | 1.000 |
| Mixed-case full recall | 1.000 |
| Retrieval Recall@3 | 0.563 |
| Retrieval Precision@3 | 0.800 |
| Retrieval MRR | 1.000 |
| Retrieval nDCG@3 | 0.970 |
| Retrieval judgment coverage@3 | 1.000 |
| Retrieval irrelevant-result rate@3 | 0.000 |
| Citation validity | 1.000 |
| Citation support | 1.000 |
| Hallucinated line-number rate | 0.000 |
| Question relevance | 1.000 |
| GitHub ingestion expectation pass rate | 1.000 |
| GitHub persisted-source privacy pass rate | 1.000 |
| Interview score accuracy | 1.000 |
| Interview completion rate | 1.000 |
| Feedback expectation pass rate | 1.000 |
| Raw-answer privacy pass rate | 1.000 |
| Prompt-injection pass rate | 1.000 |
| Estimated model cost | $0.00 |

Binary retrieval metrics treat grades 2–3 as relevant; nDCG uses all four grades.
Every returned top-three result is explicitly judged, while the fixture also
lists known-relevant candidates that were not returned. Mixed multi-file cases
can have seven relevant items while K remains three, so the corpus-wide Recall@3
gate is 0.55 and the observed value stays at an honest 0.563. MRR remains 1.0;
nDCG and irrelevant-result rate prevent the lower recall floor from hiding weak
ordering.

The production comparison evaluates local lexical, Neon lexical, Neon
vector-only, and Neon hybrid retrieval over these exact bounded queries:

```bash
.venv/bin/python scripts/export_retrieval_benchmark.py | \
  DATABASE_URL="<Neon pooled URL>" node --env-file=.env \
  scripts/run_neon_retrieval_eval.mjs
```

The 2026-09-10 Neon run measured local lexical at P@3 0.800, R@3 0.563,
MRR 1.000, nDCG@3 0.970, coverage 1.000, irrelevant 0.000, and 0.55 ms. Neon
lexical measured 0.756 / 0.531 / 0.933 / 0.913 / 0.956 / 0.044 at 49.64 ms.
Vector measured 0.644 / 0.453 / 0.756 / 0.738 / 0.756 / 0.244 at 24.18 ms;
hybrid measured 0.733 / 0.516 / 0.900 / 0.872 / 0.867 / 0.133 at 38.12 ms.
The vector query batch cost $0.00001746. Only local lexical passed every gate,
so it is the deployment default. Candidate failures remain visible in
`evals/baselines/retrieval-neon-production.json`; no gate was weakened.

Judgment coverage is not required to be perfect for candidate strategies:
unjudged results already receive relevance zero in nDCG and irrelevant-rate, so
an exact coverage requirement would double-penalize the same uncertainty. The
0.90 floor still prevents comparisons from silently outrunning the labels.
The credentialed `gpt-5.4-mini` baseline covers six reviews, three injections,
and three interviews. Finding precision/recall/accuracy, citation validity and
support, question relevance, injection pass, interview citation validity,
model-backed rate, and answer privacy are 1.000. Interview exact-score accuracy
is 0.333 while within-one agreement is 0.833, above the fixed 0.80 gate. There
were zero schema failures. The run used 16,411 input and 3,659 output tokens,
averaged 2,941 ms end-to-end (5,706 ms p95), and cost $0.028781 total /
$0.004797 per review. These narrow fixtures do not establish general quality.

Local cache evidence is tracked separately from quality: one container smoke on
2026-09-08 measured ~111 ms cold versus ~8.6 ms after a retrieval-cache hit.
It proves the cache path works but is too small to claim a general latency win.

## Human Oversight

V1 is read-only. The system may review, ask questions, and recommend work, but
it cannot comment, commit, merge, or otherwise mutate a repository. Any future
external mutation needs an explicit per-action approval and an audit record.

Model output is advisory. Findings surface evidence and citations so the user
can inspect the reasoning. Invalid or unsafe output is rejected, retried once
where appropriate, and then replaced by a clearly labeled deterministic
fallback.

## Change Record

For every material prompt, model, retrieval, schema, or guardrail change:

1. Record the version/configuration and motivation.
2. Run the same applicable eval slice.
3. Report quality, latency, and cost deltas.
4. Document known failure modes and the decision to ship, revise, or revert.
