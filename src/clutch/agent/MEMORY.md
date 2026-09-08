# Agent Memory

## Current state

`review_graph.py` compiles one linear typed LangGraph workflow:

```text
parse_code -> static_review -> retrieve_principles -> synthesize_review
  -> validate_findings -> generate_questions
```

Each node/tool/retriever/generation/guardrail stage has an explicit observation
span. Final state carries findings, questions, mode, confidence, model/tokens,
and safe fallback metadata to `ReviewService`.

`mcp_server/` is the separate read-only GitHub boundary and is not another
agent. It exposes three tools over stdio or stateless Streamable HTTP.

## Decisions

- Keep one agent; no planner/critic/supervisor without eval evidence.
- Never trace graph state or raw source. Trace hashes, counts, categories,
  citations, model/tokens, timing, and fallback category only.
- Revalidate line ranges and citation allowlists after structured synthesis.
- Generate at most three deterministic questions until broader question evals
  justify adaptive generation.

## Known gaps

- Interview orchestration is a separate deterministic service, not yet an
  adaptive LangGraph flow.
- Live OpenAI and Langfuse behavior remains unverified without credentials.
