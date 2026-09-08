# LLM Memory

## Current state

`providers.py` defines provider-neutral review context/output, an OpenAI
Responses provider, deterministic fallback, and `ModelRouter`. The OpenAI path
uses `responses.parse`, strict Pydantic output, `store=False`, a bounded output
cap, no SDK retries, and exactly one application validation retry.

`ProviderReview` carries safe model name, input/output token counts, and a
category-only fallback reason. The graph records these in redacted spans; raw
provider payloads and prompts are never logged.

`spend.py` conservatively reserves completion and embedding costs before calls.
The local counter is process-scoped; Redis uses an atomic UTC-day counter across
replicas. Per-call/daily ceilings default to $0.10/$1.00. Unknown models require
explicit price configuration, and an unavailable shared counter blocks paid
calls so the review router can fall back safely.

## Decisions

- Missing key reports `model_not_configured`; provider failures expose only the
  exception class to safe metadata before static fallback.
- Unknown citations or impossible source lines invalidate the entire model
  result instead of presenting partially trusted output.
- `gpt-5.4-mini` and `text-embedding-3-small` are configurable defaults, not
  permanent model choices.
- Built-in prices are $0.75/$4.50 per million input/output tokens for
  `gpt-5.4-mini` and $0.02 per million input tokens for
  `text-embedding-3-small`, verified against official OpenAI model pages on
  2026-09-08; operators must review or override them when changing models.

## Known gaps

- No credentialed accuracy/schema-failure/latency/token/cost baseline yet.
- The planned OpenAI-vs-Claude comparison waits for the same expanded eval set
  and a later `ModelProvider` implementation for Claude.
