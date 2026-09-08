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
- Grounding: citation presence and citation faithfulness.
- Reliability: schema-valid response rate, retry rate, and fallback rate.
- Guardrails: prompt-injection pass rate and prohibited-tool-call count.
- System: end-to-end/node latency, tokens, estimated cost, and cache hit rate.

## Gates

- Deterministic unit and API tests must pass on every change.
- The compact golden and injection suites gate every pull request and main push.
- Prompt-injection pass rate is 100% for the committed adversarial suite.
- Model or retrieval changes may not materially regress finding recall,
  citation faithfulness, or hallucinated-line rate without a documented review.
- Full and potentially costly model evals run manually or on a controlled
  schedule; CI uses deterministic/frozen paths.

Deterministic thresholds are checked by the committed eval runner. Credentialed
model thresholds will be added only after a measured baseline rather than being
invented in advance.

## Current Baseline

Dataset version `2026-09-08.v5` runs the real review graph with model routing
forced to the deterministic fallback, then runs the actual interview service and
final-report generator against in-memory privacy-safe repositories. The three
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
| Retrieval Recall@3 | 0.559 |
| Retrieval Precision@3 | 0.786 |
| Retrieval MRR | 1.000 |
| Retrieval nDCG@3 | 0.934 |
| Retrieval judgment coverage@3 | 1.000 |
| Retrieval irrelevant-result rate@3 | 0.044 |
| Citation faithfulness | 1.000 |
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
gate is 0.55 and the observed value stays at an honest 0.559. MRR remains 1.0;
nDCG and irrelevant-result rate prevent the lower recall floor from hiding weak
ordering.
The perfect finding and interview scores establish narrow regression coverage
for deterministic rules; they are not evidence of general review quality.
Invalid structured-output rate is deliberately reported as unmeasured for this
static run and will be recorded after the first controlled live-model baseline.

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
