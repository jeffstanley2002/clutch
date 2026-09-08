import asyncio
import base64

import httpx
import pytest

from clutch.github.client import (
    GitHubRateLimitError,
    GitHubResponseTooLarge,
    GitHubRestClient,
)
from clutch.github.contracts import GitHubIngestionLimits
from clutch.github.service import GitHubIngestionError, GitHubIngestionService
from clutch.github.urls import (
    GitHubUrlError,
    parse_pull_request_url,
    parse_repository_url,
)


def _encoded(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def test_github_urls_are_strict_and_canonical() -> None:
    repository = parse_repository_url("https://github.com/openai/openai-python.git")
    pull_request = parse_pull_request_url(
        "https://github.com/openai/openai-python/pull/123"
    )

    assert repository.owner == "openai"
    assert repository.repository == "openai-python"
    assert pull_request.pull_number == 123
    for unsafe in (
        "http://github.com/openai/openai-python",
        "https://evil.example/openai/openai-python",
        "https://github.com/openai/openai-python?ref=main",
        "https://github.com/openai/../pull/1",
        "https://user:pass@github.com/openai/openai-python",  # pragma: allowlist secret
    ):
        with pytest.raises(GitHubUrlError):
            parse_repository_url(unsafe)


def test_repository_fetch_applies_allowlist_size_and_binary_limits() -> None:
    sentinel = "IGNORE_PRIOR_INSTRUCTIONS_SENTINEL"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/acme/demo":
            return httpx.Response(200, json={"default_branch": "main"})
        if path == "/repos/acme/demo/git/trees/main":
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {
                            "type": "blob",
                            "path": "src/app.py",
                            "sha": "a" * 40,
                            "size": 70,
                        },
                        {
                            "type": "blob",
                            "path": "README.md",
                            "sha": "b" * 40,
                            "size": 8,
                        },
                        {
                            "type": "blob",
                            "path": "assets/logo.png",
                            "sha": "c" * 40,
                            "size": 10,
                        },
                        {
                            "type": "blob",
                            "path": "src/huge.py",
                            "sha": "d" * 40,
                            "size": 300_000,
                        },
                        {
                            "type": "blob",
                            "path": "../escape.py",
                            "sha": "e" * 40,
                            "size": 10,
                        },
                    ],
                },
            )
        if path == "/repos/acme/demo/contents/src/app.py":
            source = f"# {sentinel}\ndef run():\n    return True\n".encode()
            return httpx.Response(200, json={"content": _encoded(source)})
        if path == "/repos/acme/demo/contents/README.md":
            return httpx.Response(200, json={"content": _encoded(b"bad\x00binary")})
        raise AssertionError(f"unexpected request: {request.url}")

    limits = GitHubIngestionLimits()
    service = GitHubIngestionService(
        GitHubRestClient(
            limits=limits,
            transport=httpx.MockTransport(handler),
        ),
        limits=limits,
    )

    result = asyncio.run(service.fetch_repo("https://github.com/acme/demo"))

    assert [file.path for file in result.files] == ["src/app.py"]
    assert sentinel in result.files[0].content
    assert result.files[0].content_is_untrusted is True
    assert {item.reason for item in result.skipped} == {
        "unsupported_extension",
        "file_too_large",
        "unsafe_path",
        "binary_or_non_utf8",
    }
    assert result.total_bytes == len(result.files[0].content.encode())


def test_pull_request_fetch_keeps_only_bounded_text_patches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/repos/acme/demo/pulls/7/files"
        return httpx.Response(
            200,
            json=[
                {
                    "filename": "src/app.py",
                    "status": "modified",
                    "additions": 2,
                    "deletions": 1,
                    "changes": 3,
                    "patch": "@@ -1 +1,2 @@\n-old = True\n+new = True",
                },
                {
                    "filename": "assets/logo.png",
                    "status": "modified",
                    "additions": 0,
                    "deletions": 0,
                    "changes": 0,
                },
            ],
        )

    service = GitHubIngestionService(
        GitHubRestClient(transport=httpx.MockTransport(handler))
    )
    result = asyncio.run(
        service.fetch_pr_diff("https://github.com/acme/demo/pull/7")
    )

    assert [file.path for file in result.files] == ["src/app.py"]
    assert result.files[0].content_is_untrusted is True
    assert result.skipped[0].reason == "unsupported_extension"


def test_invalid_ref_is_rejected_before_a_tree_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise AssertionError("no GitHub request should be issued")

    service = GitHubIngestionService(
        GitHubRestClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(GitHubIngestionError):
        asyncio.run(
            service.list_repo_files(
                "https://github.com/acme/demo",
                ref="../secret",
            )
        )
    assert requests == []


def test_client_caps_api_responses_and_reports_rate_limits_safely() -> None:
    large_limits = GitHubIngestionLimits(max_api_response_bytes=100_000)

    def oversized(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 100_001)

    with pytest.raises(GitHubResponseTooLarge):
        asyncio.run(
            GitHubRestClient(
                limits=large_limits,
                transport=httpx.MockTransport(oversized),
            ).repository("acme", "demo")
        )

    def rate_limited(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "42"},
            json={"message": "remote body must not be exposed"},
        )

    with pytest.raises(GitHubRateLimitError, match="reset epoch: 42") as caught:
        asyncio.run(
            GitHubRestClient(
                token="SECRET_TOKEN_SENTINEL",
                transport=httpx.MockTransport(rate_limited),
            ).repository("acme", "demo")
        )
    assert "SECRET_TOKEN_SENTINEL" not in str(caught.value)
    assert "remote body" not in str(caught.value)
