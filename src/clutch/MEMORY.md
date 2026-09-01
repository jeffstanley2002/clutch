# Core Package Memory

## Current State

`src/clutch` contains shared Pydantic schemas and the first deterministic
review service.

Important files:

- `schemas.py`: API and future model contracts for review findings,
  interview questions, feedback reports, and progress snapshots.
- `review/static.py`: small deterministic rule set used by Day 1 `/review`.

## Decisions

- Pydantic models are the boundary objects from the first code day onward.
- Static review returns `CodeFinding` models directly, not raw dictionaries.
- The fallback "no obvious deterministic issues" finding is explicit so the
  UI always has a structured result to display.

## Known Gaps

- Static rules are intentionally shallow and should be replaced or wrapped by
  parser, retrieval, and LangGraph layers in later Phase 1 work.

