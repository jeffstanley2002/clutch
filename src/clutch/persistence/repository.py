"""Persistence adapters for review results."""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clutch.persistence.contracts import PersistedFinding, ReviewPersistenceRecord
from clutch.persistence.database import create_session_factory, database_url_from_env
from clutch.persistence.models import (
    GeneratedQuestionModel,
    ReviewFindingModel,
    ReviewSessionModel,
)


class ReviewRecorder(Protocol):
    """Minimal application-facing interface for durable review metadata."""

    async def record_review(self, record: ReviewPersistenceRecord) -> None: ...


class ReviewFindingReader(Protocol):
    """Read only the privacy-reduced findings needed by final feedback."""

    async def get_findings(self, review_session_id: str) -> list[PersistedFinding]: ...


class NullReviewRecorder:
    """No-op local fallback used when no database URL is configured."""

    async def record_review(self, record: ReviewPersistenceRecord) -> None:
        return None

    async def get_findings(self, review_session_id: str) -> list[PersistedFinding]:
        return []


class InMemoryReviewRecorder:
    """Process-local review history for the no-database development path."""

    def __init__(self) -> None:
        self.records: list[ReviewPersistenceRecord] = []

    async def record_review(self, record: ReviewPersistenceRecord) -> None:
        self.records.append(record.model_copy(deep=True))

    async def get_findings(self, review_session_id: str) -> list[PersistedFinding]:
        for record in reversed(self.records):
            if record.review_session_id == review_session_id:
                return [finding.model_copy(deep=True) for finding in record.findings]
        return []


class SqlAlchemyReviewRecorder:
    """Store privacy-reduced review records in a transactional session."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def record_review(self, record: ReviewPersistenceRecord) -> None:
        session_model = ReviewSessionModel(
            id=record.review_session_id,
            external_session_id=record.external_session_id,
            code_sha256=record.code_sha256,
            language=record.language,
            line_count=record.line_count,
            role_context=record.role_context,
            mode=record.mode,
            confidence=record.confidence,
            latency_ms=record.latency_ms,
            findings=[
                ReviewFindingModel(
                    id=str(uuid4()),
                    finding_id=finding.finding_id,
                    severity=finding.severity,
                    category=finding.category,
                    message=finding.message,
                    explanation=finding.explanation,
                    suggestion=finding.suggestion,
                    line_start=finding.line_start,
                    line_end=finding.line_end,
                    citation_ids=finding.citation_ids,
                )
                for finding in record.findings
            ],
            questions=[
                GeneratedQuestionModel(
                    id=str(uuid4()),
                    question_id=question.question_id,
                    finding_id=question.finding_id,
                    question=question.question,
                    intent=question.intent,
                    difficulty=question.difficulty,
                    citation_ids=question.citation_ids,
                )
                for question in record.questions
            ],
        )
        async with self._session_factory() as session:
            session.add(session_model)
            await session.commit()

    async def get_findings(self, review_session_id: str) -> list[PersistedFinding]:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(ReviewFindingModel)
                .where(ReviewFindingModel.review_session_id == review_session_id)
                .order_by(ReviewFindingModel.finding_id)
            )
            findings = list(result)
        return [
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
            for finding in findings
        ]


def review_recorder_from_env() -> ReviewRecorder:
    """Build the database recorder only when durable storage is configured."""

    database_url = database_url_from_env()
    if not database_url:
        return IN_MEMORY_REVIEW_RECORDER
    _, session_factory = create_session_factory(database_url)
    return SqlAlchemyReviewRecorder(session_factory)


def review_finding_reader_from_env() -> ReviewFindingReader:
    """Build the matching privacy-safe review finding reader."""

    database_url = database_url_from_env()
    if not database_url:
        return IN_MEMORY_REVIEW_RECORDER
    _, session_factory = create_session_factory(database_url)
    return SqlAlchemyReviewRecorder(session_factory)


IN_MEMORY_REVIEW_RECORDER = InMemoryReviewRecorder()
