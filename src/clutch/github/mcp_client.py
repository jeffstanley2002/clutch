"""Typed MCP client used by the application-side GitHub review workflow."""

from __future__ import annotations

import os
from typing import Any, TypeVar

from dotenv import load_dotenv
from mcp import Client
from pydantic import BaseModel

from clutch.agent.mcp_server.server import mcp as in_process_mcp
from clutch.github.contracts import (
    FetchedRepository,
    PullRequestDiff,
    RepositoryFileIndex,
)

ResultModel = TypeVar("ResultModel", bound=BaseModel)


class GitHubMcpToolError(RuntimeError):
    """Raised when the read-only GitHub MCP tool reports a handled failure."""


class GitHubMcpClient:
    """Consume GitHub data only through the MCP tool contract."""

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    async def list_repo_files(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> RepositoryFileIndex:
        return await self._call(
            "list_repo_files",
            {"repository_url": repository_url, "ref": ref},
            RepositoryFileIndex,
        )

    async def fetch_repo(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> FetchedRepository:
        return await self._call(
            "fetch_repo",
            {"repository_url": repository_url, "ref": ref},
            FetchedRepository,
        )

    async def fetch_pr_diff(self, pull_request_url: str) -> PullRequestDiff:
        return await self._call(
            "fetch_pr_diff",
            {"pull_request_url": pull_request_url},
            PullRequestDiff,
        )

    async def _call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result_model: type[ResultModel],
    ) -> ResultModel:
        async with Client(self._transport, raise_exceptions=True) as client:
            result = await client.call_tool(tool_name, arguments)
        if result.is_error:
            raise GitHubMcpToolError(_tool_error_text(tool_name, result.content))
        structured = result.structured_content
        if structured is None:
            raise RuntimeError(f"MCP tool {tool_name} returned no structured output")
        return result_model.model_validate(structured)


def github_mcp_client_from_env() -> GitHubMcpClient:
    load_dotenv()
    mcp_url = os.getenv("GITHUB_MCP_URL", "").strip()
    return GitHubMcpClient(mcp_url or in_process_mcp)


def _tool_error_text(tool_name: str, content: list[Any]) -> str:
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            prefix = f"Error executing tool {tool_name}: "
            message = text.strip()
            return message.removeprefix(prefix)
    return f"GitHub MCP tool {tool_name} failed"
