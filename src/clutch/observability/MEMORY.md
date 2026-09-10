# Observability Memory

## Current state

Null, in-memory test, and Langfuse implementations share explicit span
contracts. Review traces include root request, parse, static tool, retriever,
synthesis generation, validation guardrail, question generation, fallback, and
persistence spans. Interview traces cover the turn root, retrieval, assessment,
fallback, persistence, and deterministic final aggregation.

Inputs/outputs are allowlisted derived metadata: hashes, counts, categories,
citations, timing, native model/version/token/cost fields, and safe failure
category. Sensitive keys and Bearer tokens are redacted again by the client
mask. Sampling is validated in [0,1], automatic decorator IO capture stays
disabled, and shutdown flushes spans.
Review requests also explicitly flush Langfuse after the root span closes so
local/hosted demo traces appear promptly.

`scripts/audit_langfuse_trace.py` performs a read-only structural audit through
the v2 API and uses the legacy projection only while v2 fields are incomplete.
It never prints trace IO. Trace `9eb43ed5061418a571c4bb08b8ac2396`
demonstrates a passing forced-fallback audit with typed
`model_not_configured` categories and ten redacted observations.

## Decisions

- Never pass graph state, source, prompt, provider payload, or answers to the
  observer.
- Tracing is no-op unless explicitly enabled with both keys.
- Langfuse Cloud can expose v4 observations before every projection is complete;
  the audit fails closed and may read the legacy projection during that window.

## Known gaps

- Model-backed trace `24bc72c845a001e6d876e883f9de7c92` has all eight
  required spans plus native model/version/usage and latency, but the Japan
  Cloud API still projects both generation costs as empty after the SDK and
  documented `gen_ai.usage.cost` forms were emitted. Do not claim a passing
  native-cost audit until readback succeeds or Langfuse resolves the projection.
- Live Langfuse credentials authenticated on 2026-09-09, but the current local
  keys must be rotated before hosted deployment because earlier environment
  inspection surfaced secret values.
