# Core Package Memory

## Current State

`src/clutch` contains shared Pydantic schemas, Python parsing, and the first
deterministic review service.

Important files:

- `schemas.py`: API and future model contracts for review findings, parsed code
  chunks, interview questions, feedback reports, and progress snapshots.
- `parsing/python.py`: tree-sitter parser for Python snippets.
- `review/static.py`: small deterministic rule set used by Day 1 `/review`.

## Decisions

- Pydantic models are the boundary objects from the first code day onward.
- Static review returns `CodeFinding` models directly, not raw dictionaries.
- Parser output uses Pydantic `ParsedCode`/`CodeChunk` objects so future
  retrieval and agent context assembly can consume typed structures.
- The fallback "no obvious deterministic issues" finding is explicit so the
  UI always has a structured result to display.

## Known Gaps

- Static rules are intentionally shallow and should be replaced or wrapped by
  retrieval and LangGraph layers in later Phase 1 work.
- Parser supports Python only.
