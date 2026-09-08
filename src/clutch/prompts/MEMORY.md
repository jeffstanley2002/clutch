# Prompt Memory

## Current state

`review_system_v1.txt` is the packaged versioned system instruction.
`review.py` builds a typed `PromptBundle` from at most six parsed chunks, 12,000
source characters, six retrieved principles, deterministic leads, language,
and role context.

Prompt-regression and injection tests run in CI through the real review graph.

## Decisions

- Source is serialized as a JSON `untrusted_code` value and explicitly labelled
  data, so it cannot close a hand-written delimiter.
- The prompt names the only allowed citation IDs; provider validation enforces
  the same allowlist after generation.
- Prompt files are package data and changes require the deterministic eval gate.

## Known gaps

- Live-model prompt quality and failure modes need a controlled credentialed
  baseline against mixed and clean-negative fixtures.
