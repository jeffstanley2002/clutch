"""Application service for progress summaries and durable snapshots."""

from __future__ import annotations

from clutch.progress.repository import (
    ProgressRepository,
    progress_repository_from_env,
)
from clutch.schemas import ProgressSnapshot


class ProgressService:
    def __init__(self, repository: ProgressRepository | None = None) -> None:
        self._repository = repository or progress_repository_from_env()

    async def summarize(self, profile_id: str) -> ProgressSnapshot:
        return await self._repository.summarize(profile_id)

    async def save_snapshot(self, profile_id: str) -> ProgressSnapshot:
        snapshot = await self._repository.summarize(profile_id)
        await self._repository.save_snapshot(snapshot)
        return snapshot


progress_service = ProgressService()
