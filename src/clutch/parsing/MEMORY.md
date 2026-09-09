# Parsing Memory

## Current State

`src/clutch/parsing/python.py` uses tree-sitter with the Python grammar to
parse pasted Python source into Pydantic `ParsedCode` and `CodeChunk` models.

The parser currently emits:

- Class chunks.
- Function chunks, including methods.
- A module fallback chunk when no class/function definitions are present.
- A `has_syntax_error` flag from tree-sitter.

## Decisions

- Parsing is internal backend context; `/review` returns a `ReviewResponse` with
  findings, questions, mode, confidence, citations, request ID, and latency.
- Tree-sitter dependencies are core runtime dependencies because `/review`
  now calls the parser on every request.
- The parser preserves line ranges so review findings, retrieval, and future
  agent context can point back to source locations.

## Known Gaps

- Python is the only supported language.
- Multi-file GitHub ingestion composes bounded files before the existing parser;
  there is no separate public multi-file parser API.
- Syntax errors are detected but not yet surfaced as a dedicated finding.
