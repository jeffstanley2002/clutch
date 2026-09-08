"""Run the GitHub MCP server over stdio or bounded Streamable HTTP."""

from __future__ import annotations

import os
from ipaddress import ip_address

from mcp.server.transport_security import TransportSecuritySettings

from clutch.agent.mcp_server.server import mcp

DEFAULT_ALLOWED_HOSTS = "127.0.0.1:8001,localhost:8001,github-mcp:8001"


def _allowed_hosts() -> list[str]:
    configured = os.getenv("GITHUB_MCP_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS)
    hosts = [host.strip() for host in configured.split(",") if host.strip()]
    if not hosts:
        raise ValueError("GITHUB_MCP_ALLOWED_HOSTS must contain at least one host")
    return hosts


def _bind_host() -> str:
    host = os.getenv("CLUTCH_MCP_HOST", "127.0.0.1").strip()
    try:
        parsed = ip_address(host)
    except ValueError as exc:
        raise ValueError("CLUTCH_MCP_HOST must be an IP address") from exc
    if not (parsed.is_loopback or parsed.is_unspecified):
        raise ValueError("CLUTCH_MCP_HOST must be loopback or an unspecified address")
    return host


def main() -> None:
    transport = os.getenv("CLUTCH_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run("stdio")
        return
    if transport != "streamable-http":
        raise ValueError(
            "CLUTCH_MCP_TRANSPORT must be 'stdio' or 'streamable-http'"
        )

    mcp.run(
        "streamable-http",
        host=_bind_host(),
        port=8001,
        stateless_http=True,
        json_response=True,
        max_request_body_size=65_536,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=_allowed_hosts(),
            allowed_origins=[],
        ),
    )


if __name__ == "__main__":
    main()
