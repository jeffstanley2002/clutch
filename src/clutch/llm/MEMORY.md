# LLM Memory

## Current state

`providers.py` defines provider-neutral review/question/assessment contracts, an
OpenAI Responses provider, labeled deterministic fallbacks, and `ModelRouter`. The
OpenAI path uses `responses.parse`, strict Pydantic output, `store=False`, a
bounded output cap, no SDK retries, and exactly one application validation
retry.

`ProviderReview` carries safe model name, input/output token counts, attempt
count, validation-failure count, and safe optional diagnostics.
Pydantic enforces failures <= attempts. The graph records these in redacted
spans; raw provider payloads and prompts are never logged. Provider attempts now
emit warning logs with only model name, attempt counts, exception class, and a
small allowlisted safe failure detail.

`spend.py` conservatively reserves completion and embedding costs before calls.
The local counter is process-scoped; Redis uses an atomic UTC-day counter across
replicas. Per-call/daily ceilings default to $0.10/$1.00. Unknown models require
explicit price configuration, and an unavailable shared counter blocks paid
calls so the review router can fall back before invoking the provider. Review,
question, and assessment failures expose only labeled static/retrieval,
template, and rule-based output.

## Decisions

- Missing key reports `model_not_configured`; provider failures expose only the
  safe category/counters. Fallback output never claims to be AI-generated, and
  a typed error is reserved for combined review/fallback failure.
- Unknown citations or impossible source lines invalidate the entire model
  result instead of presenting partially trusted output. Known citation IDs are
  canonicalized from the local knowledge base so harmless title/URL paraphrases
  do not reject an otherwise grounded model response.
- `gpt-5.4-mini` and `text-embedding-3-small` are configurable defaults, not
  permanent model choices.
- Built-in prices are $0.75/$4.50 per million input/output tokens for
  `gpt-5.4-mini` and $0.02 per million input tokens for
  `text-embedding-3-small`, verified against official OpenAI model pages on
  2026-09-08; operators must review or override them when changing models.

## Known gaps

- The capped `gpt-5.4-mini` baseline passed at $0.028781 total, with zero schema
  failures. Interview exact-score agreement remains only 0.333 despite 0.833
  within-one agreement.
- Claude remains outside v1; the provider-neutral boundary allows a later
  controlled comparison if product evidence justifies it.
