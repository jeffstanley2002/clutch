"""Progress aggregation over in-memory or PostgreSQL review history."""

from __future__ import annotations

from collections import Counter
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clutch.persistence.contracts import PersistedFinding, ReviewPersistenceRecord
from clutch.persistence.database import create_session_factory, database_url_from_env
from clutch.persistence.models import (
    ProgressSnapshotModel,
    ReviewFindingModel,
    ReviewSessionModel,
)
from clutch.persistence.repository import (
    IN_MEMORY_REVIEW_RECORDER,
    InMemoryReviewRecorder,
)
from clutch.schemas import ProgressSnapshot

TASKS_BY_CATEGORY = {
    "correctness": "Practice explicit failure cases and boundary-focused tests.",
    "design": "Refactor one large or duplicated unit into named responsibilities.",
    "maintainability": "Remove temporary signals and make tradeoffs explicit.",
    "readability": "Rewrite one unit around clearer names and control flow.",
    "security": "Practice parameterization and explicit trust boundaries.",
    "testing": "Add happy-path, edge-case, and failure-path tests.",
}


class ProgressRepository(Protocol):
    async def summarize(self, profile_id: str) -> ProgressSnapshot: ...

    async def save_snapshot(self, snapshot: ProgressSnapshot) -> None: ...


class InMemoryProgressRepository:
    def __init__(self, review_store: InMemoryReviewRecorder) -> None:
        self._review_store = review_store
        self.snapshots: list[ProgressSnapshot] = []

    async def summarize(self, profile_id: str) -> ProgressSnapshot:
        records = [
            record
            for record in self._review_store.records
            if record.external_session_id == profile_id
        ]
        return _build_snapshot(profile_id, records)

    async def save_snapshot(self, snapshot: ProgressSnapshot) -> None:
        self.snapshots.append(snapshot.model_copy(deep=True))


class SqlAlchemyProgressRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def summarize(self, profile_id: str) -> ProgressSnapshot:
        statement = (
            select(ReviewSessionModel, ReviewFindingModel)
            .join(
                ReviewFindingModel,
                ReviewFindingModel.review_session_id == ReviewSessionModel.id,
            )
            .where(ReviewSessionModel.external_session_id == profile_id)
            .order_by(ReviewSessionModel.created_at, ReviewFindingModel.id)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()

        records_by_id: dict[str, ReviewPersistenceRecord] = {}
        for review, finding in rows:
            record = records_by_id.setdefault(
                review.id,
                ReviewPersistenceRecord.model_validate(
                    {
                        "review_session_id": review.id,
                        "external_session_id": review.external_session_id,
                        "code_sha256": review.code_sha256,
                        "language": review.language,
                        "line_count": review.line_count,
                        "role_context": review.role_context,
                        "mode": review.mode,
                        "confidence": review.confidence,
                        "latency_ms": review.latency_ms,
                    }
                ),
            )
            record.findings.append(
                PersistedFinding.model_validate(
                    {
                        "finding_id": finding.finding_id,
                        "severity": finding.severity,
                        "category": finding.category,
                        "message": finding.message,
                        "explanation": finding.explanation,
                        "suggestion": finding.suggestion,
                        "line_start": finding.line_start,
                        "line_end": finding.line_end,
                        "citation_ids": finding.citation_ids,
                    }
                )
            )
        return _build_snapshot(profile_id, list(records_by_id.values()))

    async def save_snapshot(self, snapshot: ProgressSnapshot) -> None:
        model = ProgressSnapshotModel(
            id=str(uuid4()),
            profile_id=snapshot.user_id,
            time_window=snapshot.time_window,
            improved_areas=snapshot.improved_areas,
            persistent_issues=snapshot.persistent_issues,
            next_practice_tasks=snapshot.next_practice_tasks,
            evidence_session_ids=snapshot.evidence_sessions,
        )
        async with self._session_factory() as session:
            session.add(model)
            await session.commit()


def progress_repository_from_env() -> ProgressRepository:
    database_url = database_url_from_env()
    if not database_url:
        return InMemoryProgressRepository(IN_MEMORY_REVIEW_RECORDER)
    _, session_factory = create_session_factory(database_url)
    return SqlAlchemyProgressRepository(session_factory)


def _build_snapshot(
    profile_id: str,
    records: list[ReviewPersistenceRecord],
) -> ProgressSnapshot:
    if not records:
        return ProgressSnapshot(
            user_id=profile_id,
            time_window="No review sessions yet",
            next_practice_tasks=[
                "Complete two code reviews with the same profile to reveal patterns."
            ],
        )

    category_counts = Counter(
        finding.category for record in records for finding in record.findings
    )
    latest_categories = {finding.category for finding in records[-1].findings}
    earlier_categories = {
        finding.category for record in records[:-1] for finding in record.findings
    }
    improved = sorted(earlier_categories - latest_categories)
    persistent = sorted(
        category for category, count in category_counts.items() if count >= 2
    )
    focus_categories = persistent or sorted(latest_categories)
    tasks = [TASKS_BY_CATEGORY[category] for category in focus_categories[:3]]
    return ProgressSnapshot(
        user_id=profile_id,
        time_window=f"{len(records)} review session(s)",
        improved_areas=[str(category) for category in improved],
        persistent_issues=[str(category) for category in persistent],
        next_practice_tasks=tasks,
        evidence_sessions=[record.review_session_id for record in records],
    )
