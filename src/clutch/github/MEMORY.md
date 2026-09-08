# GitHub Memory

## Current state

GitHub ingestion is GET-only and bounded. URL parsing accepts strict HTTPS
`github.com` repo/PR URLs; the API client targets fixed `api.github.com`, rejects
redirects/oversized bodies, applies short timeouts, and never returns provider
bodies or tokens in errors.

The service caps tree entries, files, per-file bytes, total bytes, and PR patch
bytes; allowlists text/code extensions and rejects unsafe paths, binary, NUL,
or non-UTF-8 content. Every content-bearing object is marked untrusted.

The application calls `list_repo_files`, `fetch_repo`, or `fetch_pr_diff`
through `GitHubMcpClient`, using in-process MCP locally or a configured
Streamable HTTP URL in containers/cloud.

## Decisions

- No GitHub mutation method exists.
- Public repositories work without a token; private/rate-limited reads use an
  optional backend/MCP-only scoped token.
- Only selected Python content enters the current review path and it remains
  request-scoped.

## Known gaps

- Credentialed private-repository verification needs a user-provided read-only
  token. Add more languages only after parser support exists.
