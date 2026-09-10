# Agent Memory

## Current state

`review_graph.py` compiles one linear typed LangGraph workflow:

```text
parse_code -> static_review -> retrieve_principles -> synthesize_review
  -> validate_findings -> generate_questions
```

Each node/tool/retriever/generation/guardrail stage has an explicit observation
span. Final state carries findings, questions, mode, confidence, model/tokens,
attempt counts, validation-failure counts, prompt versions, costs, and safe
failure categories to `ReviewService`.

`mcp_server/` is the separate read-only GitHub boundary and is not another
agent. It exposes three tools over stdio or stateless Streamable HTTP.

## Decisions

- Keep one agent; no planner/critic/supervisor without eval evidence.
- Never trace graph state or raw source. Trace hashes, counts, categories,
  citations, model/tokens, timing, and safe failure category only.
- Revalidate line ranges and citation allowlists after structured synthesis.
- Prefer model review; provider/config/validation/budget failure returns labeled
  `static_fallback` or `retrieval_only`, and only combined path failure errors.
- Generate at most three grounded `questions.v1` model questions; cite existing
  findings and supplied citation IDs. Failure returns template questions.

## Known gaps

- Interview orchestration is a separate service with model-backed assessment and
  deterministic final aggregation, not a second agent.
- The capped live baseline passes. Adaptive questions between interview turns
  and SSE remain deferred.
