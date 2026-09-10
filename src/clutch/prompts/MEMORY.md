# Prompt Memory

## Current state

`review_system_v2.txt`, `questions_system_v1.txt`, and
`interview_assessment_system_v1.txt` are the packaged versioned instructions.
Builders create bounded typed bundles for review synthesis, grounded question
generation, and answer assessment.

Prompt-regression and injection tests run in CI through the real review graph.

## Decisions

- Source is serialized as a JSON `untrusted_code` value and explicitly labelled
  data, so it cannot close a hand-written delimiter.
- The prompt names the only allowed citation IDs; provider validation enforces
  the same allowlist after generation.
- Prompt files are package data. `manifest.json` stores version/content SHA-256;
  CI rejects unversioned prompt text changes.

## Known gaps

- The capped `gpt-5.4-mini` baseline passes current mandatory gates. Broader
  human labels and model comparisons remain future work.
