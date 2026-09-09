"""Typed records allowed to cross the persistence boundary."""

from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, Field

from clutch.schemas import (
    FindingCategory,
    FindingSeverity,
    OutputOrigin,
    ReviewMode,
    ReviewRequest,
    ReviewResponse,
    StageProvenance,
    SupportedLanguage,
)


class PersistedFinding(BaseModel):
    """Finding fields safe to retain; raw source evidence is excluded."""

    finding_id: str
    severity: FindingSeverity
    category: FindingCategory
    message: str
    explanation: str
    suggestion: str
    line_start: int | None = None
    line_end: int | None = None
    citation_ids: list[str] = Field(default_factory=list)
    origin: OutputOrigin = "deterministic_static"


class PersistedQuestion(BaseModel):
    """Generated question fields safe to retain."""

    question_id: str
    finding_id: str | None = None
    question: str
    intent: str
    difficulty: str
    citation_ids: list[str] = Field(default_factory=list)
    origin: OutputOrigin = "template_generated"


class ReviewPersistenceRecord(BaseModel):
    """Derived review metadata with no raw submitted source or evidence."""

    review_session_id: str
    external_session_id: str | None = None
    code_sha256: str = Field(..., min_length=64, max_length=64)
    language: SupportedLanguage
    line_count: int = Field(..., ge=1)
    role_context: str
    mode: ReviewMode
    confidence: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float = Field(..., ge=0.0)
    findings: list[PersistedFinding] = Field(default_factory=list)
    questions: list[PersistedQuestion] = Field(default_factory=list)
    provenance: list[StageProvenance] = Field(default_factory=list)


def build_review_persistence_record(
    request: ReviewRequest,
    response: ReviewResponse,
) -> ReviewPersistenceRecord:
    """Reduce request/response data to the explicitly allowed durable shape."""

    return ReviewPersistenceRecord(
        review_session_id=response.request_id,
        external_session_id=request.session_id,
        code_sha256=sha256(request.code.encode("utf-8")).hexdigest(),
        language=request.language,
        line_count=max(1, len(request.code.splitlines())),
        role_context=request.role_context,
        mode=response.mode,
        confidence=response.confidence,
        latency_ms=response.latency_ms,
        provenance=response.provenance,
        findings=[
            PersistedFinding(
                finding_id=finding.id,
                severity=finding.severity,
                category=finding.category,
                message=finding.message,
                explanation=finding.explanation,
                suggestion=finding.suggestion,
                line_start=finding.line_start,
                line_end=finding.line_end,
                citation_ids=[
                    citation.source_id for citation in finding.citations
                ],
                origin=finding.origin,
            )
            for finding in response.findings
        ],
        questions=[
            PersistedQuestion(
                question_id=question.id,
                finding_id=question.finding_id,
                question=question.question,
                intent=question.intent,
                difficulty=question.difficulty,
                citation_ids=[
                    citation.source_id for citation in question.citations
                ],
                origin=question.origin,
            )
            for question in response.questions
        ],
    )
