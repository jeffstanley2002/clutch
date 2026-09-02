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

- Parsing is internal backend context for now; `/review` still returns only
  `list[CodeFinding]`.
- Tree-sitter dependencies are core runtime dependencies because `/review`
  now calls the parser on every request.
- The parser preserves line ranges so review findings, retrieval, and future
  agent context can point back to source locations.

## Known Gaps

- Python is the only supported language.
- There is no repository/multi-file parser entry point yet.
- Syntax errors are detected but not yet surfaced as a dedicated finding.
