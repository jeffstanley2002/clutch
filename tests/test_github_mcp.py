import asyncio

import pytest
from mcp import Client

from clutch.agent.mcp_server import build_github_mcp_server
from clutch.agent.mcp_server.__main__ import _allowed_hosts, _bind_host
from clutch.github.contracts import (
    FetchedRepository,
    GitHubFile,
    PullRequestDiff,
    RepositoryFile,
    RepositoryFileIndex,
)
from clutch.github.mcp_client import GitHubMcpClient


class FakeGitHubService:
    async def list_repo_files(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> RepositoryFileIndex:
        return RepositoryFileIndex(
            owner="acme",
            repository="demo",
            ref=ref or "main",
            files=[RepositoryFile(path="app.py", sha="a" * 40, size=20)],
        )

    async def fetch_repo(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> FetchedRepository:
        return FetchedRepository(
            owner="acme",
            repository="demo",
            ref=ref or "main",
            files=[
                GitHubFile(
                    path="app.py",
                    sha="a" * 40,
                    size=20,
                    content="def run():\n    pass\n",
                )
            ],
            total_bytes=20,
        )

    async def fetch_pr_diff(self, pull_request_url: str) -> PullRequestDiff:
        return PullRequestDiff(
            owner="acme",
            repository="demo",
            pull_number=7,
        )


def test_mcp_server_exposes_exactly_three_read_only_tools() -> None:
    async def exercise() -> None:
        server = build_github_mcp_server(FakeGitHubService())  # type: ignore[arg-type]
        async with Client(server) as client:
            tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "fetch_pr_diff",
            "fetch_repo",
            "list_repo_files",
        }
        assert all(tool.annotations is not None for tool in tools.tools)
        assert all(tool.annotations.read_only_hint for tool in tools.tools if tool.annotations)
        assert all(tool.annotations.idempotent_hint for tool in tools.tools if tool.annotations)

    asyncio.run(exercise())


def test_application_client_validates_mcp_structured_output() -> None:
    async def exercise() -> None:
        server = build_github_mcp_server(FakeGitHubService())  # type: ignore[arg-type]
        client = GitHubMcpClient(server)
        result = await client.fetch_repo("https://github.com/acme/demo")

        assert result.owner == "acme"
        assert result.files[0].content_is_untrusted is True

    asyncio.run(exercise())


def test_http_transport_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLUTCH_MCP_HOST", raising=False)
    monkeypatch.delenv("GITHUB_MCP_ALLOWED_HOSTS", raising=False)

    assert _bind_host() == "127.0.0.1"
    assert "github-mcp:8001" in _allowed_hosts()


def test_http_transport_rejects_nonlocal_specific_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLUTCH_MCP_HOST", "192.0.2.10")

    with pytest.raises(ValueError, match="loopback or an unspecified address"):
        _bind_host()
