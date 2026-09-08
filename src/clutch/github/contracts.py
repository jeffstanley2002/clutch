"""Typed contracts for bounded GitHub repository and pull-request ingestion."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkipReason = Literal[
    "unsupported_extension",
    "unsafe_path",
    "file_too_large",
    "repository_file_limit",
    "repository_byte_limit",
    "binary_or_non_utf8",
    "missing_content",
    "missing_patch",
]


class GitHubIngestionLimits(BaseModel):
    """Security and cost limits applied before content enters review context."""

    model_config = ConfigDict(frozen=True)

    max_tree_entries: int = Field(default=5_000, ge=1, le=20_000)
    max_files: int = Field(default=25, ge=1, le=100)
    max_file_bytes: int = Field(default=200_000, ge=1, le=1_000_000)
    max_total_bytes: int = Field(default=1_000_000, ge=1, le=5_000_000)
    max_api_response_bytes: int = Field(
        default=8_000_000,
        ge=100_000,
        le=20_000_000,
    )


class RepositoryFile(BaseModel):
    """Safe metadata for one GitHub repository blob."""

    path: str = Field(..., min_length=1, max_length=1_000)
    sha: str = Field(..., min_length=1, max_length=80)
    size: int = Field(..., ge=0)


class SkippedGitHubFile(BaseModel):
    """A repository item omitted by a deterministic ingestion policy."""

    path: str = Field(..., min_length=1, max_length=1_000)
    reason: SkipReason


class GitHubFile(BaseModel):
    """One bounded text file; content is untrusted and never persisted by default."""

    path: str = Field(..., min_length=1, max_length=1_000)
    sha: str = Field(..., min_length=1, max_length=80)
    size: int = Field(..., ge=0)
    content: str = Field(..., max_length=1_000_000)
    content_is_untrusted: Literal[True] = True


class RepositoryFileIndex(BaseModel):
    """Bounded file listing returned by the read-only MCP tool."""

    owner: str
    repository: str
    ref: str
    files: list[RepositoryFile] = Field(default_factory=list)
    skipped: list[SkippedGitHubFile] = Field(default_factory=list)
    truncated: bool = False


class FetchedRepository(BaseModel):
    """Bounded repository text returned for an active review request."""

    owner: str
    repository: str
    ref: str
    files: list[GitHubFile] = Field(default_factory=list)
    skipped: list[SkippedGitHubFile] = Field(default_factory=list)
    total_bytes: int = Field(default=0, ge=0)
    truncated: bool = False
    content_is_untrusted: Literal[True] = True


class PullRequestPatch(BaseModel):
    """One bounded PR patch from GitHub's read-only files endpoint."""

    path: str = Field(..., min_length=1, max_length=1_000)
    status: str = Field(..., min_length=1, max_length=40)
    additions: int = Field(..., ge=0)
    deletions: int = Field(..., ge=0)
    changes: int = Field(..., ge=0)
    patch: str = Field(..., max_length=1_000_000)
    content_is_untrusted: Literal[True] = True


class PullRequestDiff(BaseModel):
    """Bounded pull-request patches returned for an active review request."""

    owner: str
    repository: str
    pull_number: int = Field(..., ge=1)
    files: list[PullRequestPatch] = Field(default_factory=list)
    skipped: list[SkippedGitHubFile] = Field(default_factory=list)
    total_bytes: int = Field(default=0, ge=0)
    truncated: bool = False
    content_is_untrusted: Literal[True] = True
