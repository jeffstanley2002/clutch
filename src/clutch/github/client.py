"""Minimal read-only GitHub REST client with bounded response bodies."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from clutch.github.contracts import GitHubIngestionLimits


class GitHubAPIError(RuntimeError):
    """Safe GitHub failure that excludes remote response bodies and credentials."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub reports an exhausted rate limit."""


class GitHubResponseTooLarge(GitHubAPIError):
    """Raised before an oversized API response is decoded."""


class GitHubRestClient:
    """Issue GET-only requests to the fixed api.github.com origin."""

    def __init__(
        self,
        *,
        token: str | None = None,
        api_version: str = "2026-03-10",
        limits: GitHubIngestionLimits | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = (token or "").strip()
        self._api_version = api_version
        self._limits = limits or GitHubIngestionLimits()
        self._transport = transport

    async def repository(self, owner: str, repository: str) -> dict[str, Any]:
        return await self._get_json(f"/repos/{owner}/{repository}")

    async def repository_tree(
        self,
        owner: str,
        repository: str,
        ref: str,
    ) -> dict[str, Any]:
        encoded_ref = quote(ref, safe="")
        return await self._get_json(
            f"/repos/{owner}/{repository}/git/trees/{encoded_ref}",
            params={"recursive": "1"},
        )

    async def repository_content(
        self,
        owner: str,
        repository: str,
        path: str,
        ref: str,
    ) -> dict[str, Any]:
        encoded_path = quote(path, safe="/")
        return await self._get_json(
            f"/repos/{owner}/{repository}/contents/{encoded_path}",
            params={"ref": ref},
        )

    async def pull_request_files(
        self,
        owner: str,
        repository: str,
        pull_number: int,
    ) -> list[dict[str, Any]]:
        result = await self._get_json(
            f"/repos/{owner}/{repository}/pulls/{pull_number}/files",
            params={"per_page": "100", "page": "1"},
        )
        if not isinstance(result, list):
            raise GitHubAPIError("GitHub returned an invalid pull-request file list")
        return result

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "clutch-read-only-review/0.1",
            "X-GitHub-Api-Version": self._api_version,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=timeout,
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            async with client.stream("GET", path, params=params) as response:
                if response.status_code in {403, 429} and (
                    response.headers.get("x-ratelimit-remaining") == "0"
                    or response.status_code == 429
                ):
                    reset = response.headers.get("x-ratelimit-reset", "unknown")
                    raise GitHubRateLimitError(
                        f"GitHub rate limit exhausted; reset epoch: {reset}"
                    )
                if response.status_code != 200:
                    raise GitHubAPIError(
                        f"GitHub read request failed with status {response.status_code}"
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._limits.max_api_response_bytes:
                        raise GitHubResponseTooLarge(
                            "GitHub response exceeded the configured byte limit"
                        )
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubAPIError("GitHub returned an invalid JSON response") from exc
