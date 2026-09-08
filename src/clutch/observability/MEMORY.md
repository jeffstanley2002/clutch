# Observability Memory

## Current state

Null, in-memory test, and Langfuse implementations share explicit span
contracts. Review traces include root request plus parse, static tool,
retriever, synthesis generation, validation guardrail, and question tool spans.

Inputs/outputs are allowlisted derived metadata: hashes, counts, categories,
citations, timing, model/tokens, and fallback class. Sensitive keys and Bearer
tokens are redacted again by the client mask. Sampling is validated in [0,1],
automatic decorator IO capture stays disabled, and shutdown flushes spans.

## Decisions

- Never pass graph state, source, prompt, provider payload, or answers to the
  observer.
- Tracing is no-op unless explicitly enabled with both keys.

## Known gaps

- Live Langfuse trace/export verification needs user-owned keys.
