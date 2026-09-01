"""Shared Pydantic contracts for API, tool, and future model boundaries."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


SupportedLanguage = Literal["python"]
FindingSeverity = Literal["low", "medium", "high"]
FindingCategory = Literal[
    "maintainability",
    "readability",
    "correctness",
    "testing",
    "design",
    "security",
]


class Citation(BaseModel):
    """A source reference that grounds review feedback."""

    source_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    url: str | None = None


class ReviewRequest(BaseModel):
    """Request for the first pasted-code review workflow."""

    code: str = Field(..., min_length=1, max_length=50_000)
    language: SupportedLanguage = "python"
    role_context: str = Field(default="backend intern", max_length=120)
    session_id: str | None = Field(default=None, max_length=120)

    @field_validator("code")
    @classmethod
    def code_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code must contain non-whitespace characters")
        return value

    @field_validator("role_context")
    @classmethod
    def normalize_role_context(cls, value: str) -> str:
        normalized = value.strip()
        return normalized or "backend intern"


class CodeFinding(BaseModel):
    """A structured code review finding."""

    id: str = Field(..., min_length=1)
    severity: FindingSeverity
    category: FindingCategory
    message: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    explanation: str = Field(..., min_length=1)
    suggestion: str = Field(..., min_length=1)
    citations: list[Citation] = Field(default_factory=list)


class InterviewQuestion(BaseModel):
    """Future contract for interviewer-style follow-up questions."""

    id: str = Field(..., min_length=1)
    finding_id: str | None = None
    question: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1)
    difficulty: Literal["easy", "medium", "hard"]
    citations: list[Citation] = Field(default_factory=list)


class FeedbackReport(BaseModel):
    """Future contract for interview feedback reports."""

    session_id: str
    strengths: list[str] = Field(default_factory=list)
    recurring_issues: list[str] = Field(default_factory=list)
    recommended_tasks: list[str] = Field(default_factory=list)
    interview_readiness_summary: str
    supporting_findings: list[CodeFinding] = Field(default_factory=list)


class ProgressSnapshot(BaseModel):
    """Future contract for cross-session progress tracking."""

    user_id: str
    time_window: str
    improved_areas: list[str] = Field(default_factory=list)
    persistent_issues: list[str] = Field(default_factory=list)
    next_practice_tasks: list[str] = Field(default_factory=list)
    evidence_sessions: list[str] = Field(default_factory=list)

