"""Application service that reviews GitHub content fetched only through MCP."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Protocol

from clutch.github.contracts import FetchedRepository, PullRequestDiff
from clutch.github.mcp_client import github_mcp_client_from_env
from clutch.github.urls import GitHubUrlError, parse_pull_request_url
from clutch.review.service import ReviewService, review_service
from clutch.schemas import (
    GitHubIngestionSummary,
    GitHubReviewRequest,
    GitHubReviewResponse,
    ReviewRequest,
)

MAX_REVIEW_SOURCE_CHARS = 48_000
PYTHON_EXTENSIONS = frozenset({".py", ".pyi"})


class GitHubReviewSourceEmpty(ValueError):
    """Raised when a bounded fetch contains no supported Python source."""


class GitHubSourceGateway(Protocol):
    async def fetch_repo(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> FetchedRepository: ...

    async def fetch_pr_diff(self, pull_request_url: str) -> PullRequestDiff: ...


class GitHubReviewService:
    def __init__(
        self,
        gateway: GitHubSourceGateway,
        reviewer: ReviewService,
    ) -> None:
        self._gateway = gateway
        self._reviewer = reviewer

    async def review(self, request: GitHubReviewRequest) -> GitHubReviewResponse:
        try:
            pull_target = parse_pull_request_url(request.source_url)
        except GitHubUrlError:
            return await self._review_repository(request)
        diff = await self._gateway.fetch_pr_diff(request.source_url)
        sources = [
            (file.path, _source_from_patch(file.patch))
            for file in diff.files
            if PurePosixPath(file.path).suffix.lower() in PYTHON_EXTENSIONS
        ]
        code, included = compose_github_review_source(sources)
        result = await self._reviewer.review(
            ReviewRequest(
                code=code,
                role_context=request.role_context,
                session_id=request.session_id,
            )
        )
        return GitHubReviewResponse(
            ingestion=GitHubIngestionSummary(
                source_type="pull_request",
                owner=diff.owner,
                repository=diff.repository,
                pull_number=pull_target.pull_number,
                files_included=included,
                skipped_file_count=len(diff.skipped),
                total_bytes=diff.total_bytes,
                truncated=diff.truncated or len(included) < len(sources),
            ),
            review=result,
        )

    async def _review_repository(
        self,
        request: GitHubReviewRequest,
    ) -> GitHubReviewResponse:
        repository = await self._gateway.fetch_repo(request.source_url, request.ref)
        sources = [
            (file.path, file.content)
            for file in repository.files
            if PurePosixPath(file.path).suffix.lower() in PYTHON_EXTENSIONS
        ]
        code, included = compose_github_review_source(sources)
        result = await self._reviewer.review(
            ReviewRequest(
                code=code,
                role_context=request.role_context,
                session_id=request.session_id,
            )
        )
        return GitHubReviewResponse(
            ingestion=GitHubIngestionSummary(
                source_type="repository",
                owner=repository.owner,
                repository=repository.repository,
                ref=repository.ref,
                files_included=included,
                skipped_file_count=len(repository.skipped),
                total_bytes=repository.total_bytes,
                truncated=repository.truncated or len(included) < len(sources),
            ),
            review=result,
        )


def compose_github_review_source(
    sources: list[tuple[str, str]],
) -> tuple[str, list[str]]:
    """Compose bounded file text exactly as the GitHub review path consumes it."""

    chunks: list[str] = []
    included: list[str] = []
    current_length = 0
    for path, source in sources:
        marker = f"# --- GitHub file: {path} (untrusted source) ---\n"
        chunk = f"{marker}{source.rstrip()}\n"
        if current_length + len(chunk) > MAX_REVIEW_SOURCE_CHARS:
            continue
        chunks.append(chunk)
        included.append(path)
        current_length += len(chunk)
    if not chunks:
        raise GitHubReviewSourceEmpty(
            "GitHub source contains no Python file within the configured limits"
        )
    return "\n".join(chunks), included


def _source_from_patch(patch: str) -> str:
    lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith(("@@", "---", "+++", "\\")):
            continue
        if line.startswith("-"):
            continue
        lines.append(line[1:] if line.startswith(("+", " ")) else line)
    return "\n".join(lines)


github_review_service = GitHubReviewService(
    gateway=github_mcp_client_from_env(),
    reviewer=review_service,
)
