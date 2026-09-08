"""Bounded read-only repository and pull-request ingestion service."""

from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv

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
    SkipReason,
)
from clutch.github.policy import (
    decode_base64_text,
    is_safe_repository_path,
    is_supported_text_path,
    is_text_patch,
)
from clutch.github.urls import parse_pull_request_url, parse_repository_url

_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


class GitHubIngestionError(ValueError):
    """Raised for invalid or over-limit GitHub content."""


class GitHubIngestionService:
    def __init__(
        self,
        client: GitHubRestClient,
        *,
        limits: GitHubIngestionLimits | None = None,
    ) -> None:
        self._client = client
        self._limits = limits or GitHubIngestionLimits()

    async def list_repo_files(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> RepositoryFileIndex:
        target = parse_repository_url(repository_url)
        resolved_ref = await self._resolve_ref(target.owner, target.repository, ref)
        tree = await self._client.repository_tree(
            target.owner,
            target.repository,
            resolved_ref,
        )
        entries = tree.get("tree", [])
        if not isinstance(entries, list):
            raise GitHubIngestionError("GitHub returned an invalid repository tree")
        if len(entries) > self._limits.max_tree_entries:
            raise GitHubIngestionError(
                "repository tree exceeds the configured entry limit"
            )

        files: list[RepositoryFile] = []
        skipped: list[SkippedGitHubFile] = []
        truncated = bool(tree.get("truncated", False))
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("type") != "blob":
                continue
            path = str(entry.get("path", ""))
            reason = _metadata_skip_reason(path, entry, self._limits)
            if reason is not None:
                skipped.append(SkippedGitHubFile(path=path or "<missing>", reason=reason))
                continue
            if len(files) >= self._limits.max_files:
                skipped.append(
                    SkippedGitHubFile(
                        path=path,
                        reason="repository_file_limit",
                    )
                )
                truncated = True
                continue
            files.append(
                RepositoryFile(
                    path=path,
                    sha=str(entry["sha"]),
                    size=int(entry["size"]),
                )
            )
        return RepositoryFileIndex(
            owner=target.owner,
            repository=target.repository,
            ref=resolved_ref,
            files=files,
            skipped=skipped,
            truncated=truncated,
        )

    async def fetch_repo(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> FetchedRepository:
        index = await self.list_repo_files(repository_url, ref)
        files: list[GitHubFile] = []
        skipped = list(index.skipped)
        total_bytes = 0
        truncated = index.truncated
        for metadata in index.files:
            if total_bytes + metadata.size > self._limits.max_total_bytes:
                skipped.append(
                    SkippedGitHubFile(
                        path=metadata.path,
                        reason="repository_byte_limit",
                    )
                )
                truncated = True
                continue
            payload = await self._client.repository_content(
                index.owner,
                index.repository,
                metadata.path,
                index.ref,
            )
            encoded_content = payload.get("content")
            if not isinstance(encoded_content, str):
                skipped.append(
                    SkippedGitHubFile(path=metadata.path, reason="missing_content")
                )
                continue
            text = decode_base64_text(encoded_content.replace("\n", ""))
            if text is None:
                skipped.append(
                    SkippedGitHubFile(
                        path=metadata.path,
                        reason="binary_or_non_utf8",
                    )
                )
                continue
            actual_size = len(text.encode("utf-8"))
            if actual_size > self._limits.max_file_bytes:
                skipped.append(
                    SkippedGitHubFile(path=metadata.path, reason="file_too_large")
                )
                continue
            if total_bytes + actual_size > self._limits.max_total_bytes:
                skipped.append(
                    SkippedGitHubFile(
                        path=metadata.path,
                        reason="repository_byte_limit",
                    )
                )
                truncated = True
                continue
            files.append(
                GitHubFile(
                    path=metadata.path,
                    sha=metadata.sha,
                    size=actual_size,
                    content=text,
                )
            )
            total_bytes += actual_size
        return FetchedRepository(
            owner=index.owner,
            repository=index.repository,
            ref=index.ref,
            files=files,
            skipped=skipped,
            total_bytes=total_bytes,
            truncated=truncated,
        )

    async def fetch_pr_diff(self, pull_request_url: str) -> PullRequestDiff:
        target = parse_pull_request_url(pull_request_url)
        assert target.pull_number is not None
        entries = await self._client.pull_request_files(
            target.owner,
            target.repository,
            target.pull_number,
        )
        patches: list[PullRequestPatch] = []
        skipped: list[SkippedGitHubFile] = []
        total_bytes = 0
        truncated = len(entries) > self._limits.max_files
        for entry in entries:
            path = str(entry.get("filename", ""))
            if not is_safe_repository_path(path):
                skipped.append(
                    SkippedGitHubFile(path=path or "<missing>", reason="unsafe_path")
                )
                continue
            if not is_supported_text_path(path):
                skipped.append(
                    SkippedGitHubFile(path=path, reason="unsupported_extension")
                )
                continue
            if len(patches) >= self._limits.max_files:
                skipped.append(
                    SkippedGitHubFile(path=path, reason="repository_file_limit")
                )
                continue
            patch = entry.get("patch")
            if not isinstance(patch, str) or not patch:
                skipped.append(SkippedGitHubFile(path=path, reason="missing_patch"))
                continue
            patch_bytes = len(patch.encode("utf-8"))
            if patch_bytes > self._limits.max_file_bytes:
                skipped.append(SkippedGitHubFile(path=path, reason="file_too_large"))
                continue
            if not is_text_patch(patch):
                skipped.append(
                    SkippedGitHubFile(path=path, reason="binary_or_non_utf8")
                )
                continue
            if total_bytes + patch_bytes > self._limits.max_total_bytes:
                skipped.append(
                    SkippedGitHubFile(path=path, reason="repository_byte_limit")
                )
                truncated = True
                continue
            patches.append(
                PullRequestPatch(
                    path=path,
                    status=str(entry.get("status", "unknown")),
                    additions=_non_negative_int(entry.get("additions")),
                    deletions=_non_negative_int(entry.get("deletions")),
                    changes=_non_negative_int(entry.get("changes")),
                    patch=patch,
                )
            )
            total_bytes += patch_bytes
        return PullRequestDiff(
            owner=target.owner,
            repository=target.repository,
            pull_number=target.pull_number,
            files=patches,
            skipped=skipped,
            total_bytes=total_bytes,
            truncated=truncated,
        )

    async def _resolve_ref(
        self,
        owner: str,
        repository: str,
        requested_ref: str | None,
    ) -> str:
        if requested_ref is None:
            metadata = await self._client.repository(owner, repository)
            requested_ref = str(metadata.get("default_branch", ""))
        normalized = requested_ref.strip()
        if (
            not _REF_RE.fullmatch(normalized)
            or normalized.endswith("/")
            or ".." in normalized.split("/")
        ):
            raise GitHubIngestionError("Git reference is invalid")
        return normalized


def github_ingestion_service_from_env() -> GitHubIngestionService:
    load_dotenv()
    limits = GitHubIngestionLimits()
    client = GitHubRestClient(
        token=os.getenv("GITHUB_TOKEN"),
        api_version=os.getenv("GITHUB_API_VERSION", "2026-03-10"),
        limits=limits,
    )
    return GitHubIngestionService(client, limits=limits)


def _metadata_skip_reason(
    path: str,
    entry: dict[str, Any],
    limits: GitHubIngestionLimits,
) -> SkipReason | None:
    if not is_safe_repository_path(path):
        return "unsafe_path"
    if not is_supported_text_path(path):
        return "unsupported_extension"
    size = entry.get("size")
    sha = entry.get("sha")
    if not isinstance(size, int) or size < 0 or not isinstance(sha, str) or not sha:
        return "missing_content"
    if size > limits.max_file_bytes:
        return "file_too_large"
    return None


def _non_negative_int(value: Any) -> int:
    return value if isinstance(value, int) and value >= 0 else 0
