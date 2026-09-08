"""Read-only GitHub ingestion with explicit untrusted-content boundaries."""

from clutch.github.client import GitHubRestClient
from clutch.github.contracts import (
    FetchedRepository,
    GitHubFile,
    GitHubIngestionLimits,
    PullRequestDiff,
    PullRequestPatch,
    RepositoryFile,
    RepositoryFileIndex,
    SkippedGitHubFile,
)
from clutch.github.service import GitHubIngestionService
from clutch.github.urls import (
    GitHubUrlError,
    RepositoryCoordinates,
    parse_pull_request_url,
    parse_repository_url,
)

__all__ = [
    "FetchedRepository",
    "GitHubFile",
    "GitHubIngestionLimits",
    "GitHubIngestionService",
    "GitHubRestClient",
    "GitHubUrlError",
    "PullRequestDiff",
    "PullRequestPatch",
    "RepositoryCoordinates",
    "RepositoryFile",
    "RepositoryFileIndex",
    "SkippedGitHubFile",
    "parse_pull_request_url",
    "parse_repository_url",
]
