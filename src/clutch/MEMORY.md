# Core Package Memory

## Current State

`src/clutch` contains shared Pydantic schemas, Python parsing, seed clean-code
retrieval, and the first deterministic review service.

Important files:

- `schemas.py`: API and future model contracts for review findings, parsed code
  chunks, interview questions, feedback reports, and progress snapshots.
- `parsing/python.py`: tree-sitter parser for Python snippets.
- `knowledge_base/clean_code.py`: seeded clean-code principles plus local
  lexical retrieval.
- `review/static.py`: small deterministic rule set used by `/review`, with
  findings grounded in retrieved seed citations.

## Decisions

- Pydantic models are the boundary objects from the first code day onward.
- Static review returns `CodeFinding` models directly, not raw dictionaries.
- Parser output uses Pydantic `ParsedCode`/`CodeChunk` objects so future
  retrieval and agent context assembly can consume typed structures.
- The fallback "no obvious deterministic issues" finding is explicit so the
  UI always has a structured result to display.
- Retrieval returns Pydantic `CleanCodePrinciple` objects with embedded
  `Citation` models, keeping the citation path structured before LLM calls
  exist.

## Known Gaps

- Static rules are intentionally shallow and should be wrapped by LangGraph and
  model-backed review in later Phase 1 work.
- Retrieval is lexical over a tiny in-memory corpus; vector-only retrieval is
  still a future Phase 1 layer.
- Parser supports Python only.
