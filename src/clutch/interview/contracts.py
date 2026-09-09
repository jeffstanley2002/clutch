"""Internal typed interview state that never retains raw answers."""

from __future__ import annotations

from pydantic import BaseModel, Field

from clutch.schemas import (
    InterviewAssessment,
    InterviewQuestion,
    InterviewStatus,
    StageProvenance,
)


class InterviewSessionState(BaseModel):
    session_id: str
    review_session_id: str | None = None
    profile_id: str | None = None
    role_context: str
    status: InterviewStatus = "active"
    current_question: InterviewQuestion | None = None
    remaining_questions: list[InterviewQuestion] = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)


class InterviewTurnRecord(BaseModel):
    session_id: str
    turn_number: int = Field(..., ge=1)
    question: InterviewQuestion
    answer_sha256: str = Field(..., min_length=64, max_length=64)
    answer_summary: str
    assessment: InterviewAssessment
    provenance: list[StageProvenance] = Field(default_factory=list)
    next_question: InterviewQuestion | None = None
    remaining_questions: list[InterviewQuestion] = Field(default_factory=list)
    status: InterviewStatus


class InterviewTurnEvidence(BaseModel):
    """Privacy-reduced turn data used to assemble final feedback."""

    turn_number: int = Field(..., ge=1)
    answer_summary: str
    assessment: InterviewAssessment
