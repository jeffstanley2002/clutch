"""Strict parsing for GitHub repository and pull-request URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import SplitResult, unquote, urlsplit

_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GitHubUrlError(ValueError):
    """Raised when a URL is not a supported canonical GitHub target."""


@dataclass(frozen=True, slots=True)
class RepositoryCoordinates:
    owner: str
    repository: str
    pull_number: int | None = None


def parse_repository_url(url: str) -> RepositoryCoordinates:
    """Parse an HTTPS github.com repository URL without accepting redirects."""

    parts = _validated_url(url)
    segments = _segments(parts.path)
    if len(segments) != 2:
        raise GitHubUrlError("expected https://github.com/OWNER/REPOSITORY")
    return RepositoryCoordinates(
        owner=_validate_owner(segments[0]),
        repository=_validate_repository(segments[1]),
    )


def parse_pull_request_url(url: str) -> RepositoryCoordinates:
    """Parse an HTTPS github.com pull-request URL."""

    parts = _validated_url(url)
    segments = _segments(parts.path)
    if len(segments) != 4 or segments[2] != "pull":
        raise GitHubUrlError(
            "expected https://github.com/OWNER/REPOSITORY/pull/NUMBER"
        )
    try:
        pull_number = int(segments[3])
    except ValueError as exc:
        raise GitHubUrlError("pull request number must be a positive integer") from exc
    if pull_number < 1:
        raise GitHubUrlError("pull request number must be a positive integer")
    return RepositoryCoordinates(
        owner=_validate_owner(segments[0]),
        repository=_validate_repository(segments[1]),
        pull_number=pull_number,
    )


def _validated_url(url: str) -> SplitResult:
    normalized = url.strip()
    if len(normalized) > 500:
        raise GitHubUrlError("GitHub URL is too long")
    parts = urlsplit(normalized)
    if parts.scheme != "https" or parts.hostname != "github.com":
        raise GitHubUrlError("only HTTPS github.com URLs are supported")
    if parts.username or parts.password or parts.port:
        raise GitHubUrlError("credentials and ports are not allowed")
    return parts


def _segments(path: str) -> list[str]:
    segments = [unquote(segment) for segment in path.strip("/").split("/")]
    if any(not segment or segment in {".", ".."} for segment in segments):
        raise GitHubUrlError("GitHub URL contains an unsafe path")
    return segments


def _validate_owner(owner: str) -> str:
    if not _OWNER_RE.fullmatch(owner):
        raise GitHubUrlError("GitHub owner is invalid")
    return owner


def _validate_repository(repository: str) -> str:
    normalized = repository.removesuffix(".git")
    if not _REPOSITORY_RE.fullmatch(normalized) or normalized in {".", ".."}:
        raise GitHubUrlError("GitHub repository name is invalid")
    return normalized
