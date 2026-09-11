# GitHub MCP Server Memory

## Current state

This is Clutch's only MCP server. It exposes exactly `list_repo_files`,
`fetch_repo`, and `fetch_pr_diff`, all annotated read-only and idempotent.

The default transport is stdio. `CLUTCH_MCP_TRANSPORT=streamable-http` enables
stateless JSON Streamable HTTP on port 8001. Local bind defaults to loopback;
Docker explicitly opts into `0.0.0.0`. DNS-rebinding protection allowlists
localhost and the internal `github-mcp` host. `/health` is dependency-free.

Known GitHub URL, ingestion, and API-read failures are raised as handled MCP
tool errors so the application client can return a recoverable API response.

## Decisions

- This is an external GitHub boundary, not a second agent.
- It has no repository mutation tool and returns typed, bounded, explicitly
  untrusted data.

## Known gaps

- Production TLS terminates at the surrounding network boundary; MCP remains
  private between FastAPI and the service.
