"""SQLAlchemy tables for durable reviews, interviews, progress, and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSON_VALUE = JSON().with_variant(JSONB, "postgresql")
EMBEDDING_DIMENSIONS = 1536


class Base(DeclarativeBase):
    """Declarative metadata root used by application code and Alembic."""


class ReviewSessionModel(Base):
    __tablename__ = "review_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_session_id: Mapped[str | None] = mapped_column(String(120), index=True)
    code_sha256: Mapped[str] = mapped_column(String(64), index=True)
    language: Mapped[str] = mapped_column(String(32))
    line_count: Mapped[int] = mapped_column(Integer)
    role_context: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    findings: Mapped[list[ReviewFindingModel]] = relationship(
        cascade="all, delete-orphan"
    )
    questions: Mapped[list[GeneratedQuestionModel]] = relationship(
        cascade="all, delete-orphan"
    )


class ReviewFindingModel(Base):
    __tablename__ = "review_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_session_id: Mapped[str] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"), index=True
    )
    finding_id: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(32), index=True)
    message: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text)
    line_start: Mapped[int | None] = mapped_column(Integer)
    line_end: Mapped[int | None] = mapped_column(Integer)
    citation_ids: Mapped[list[str]] = mapped_column(JSON_VALUE)


class GeneratedQuestionModel(Base):
    __tablename__ = "generated_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_session_id: Mapped[str] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(String(120))
    finding_id: Mapped[str | None] = mapped_column(String(120))
    question: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16))
    citation_ids: Mapped[list[str]] = mapped_column(JSON_VALUE)


class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="SET NULL"), index=True
    )
    profile_id: Mapped[str | None] = mapped_column(String(120), index=True)
    role_context: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="active")
    current_question: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    remaining_questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VALUE)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InterviewTurnModel(Base):
    __tablename__ = "interview_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    turn_number: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    answer_sha256: Mapped[str] = mapped_column(String(64))
    answer_summary: Mapped[str] = mapped_column(Text)
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProgressSnapshotModel(Base):
    __tablename__ = "progress_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(120), index=True)
    time_window: Mapped[str] = mapped_column(String(120))
    improved_areas: Mapped[list[str]] = mapped_column(JSON_VALUE)
    persistent_issues: Mapped[list[str]] = mapped_column(JSON_VALUE)
    next_practice_tasks: Mapped[list[str]] = mapped_column(JSON_VALUE)
    evidence_session_ids: Mapped[list[str]] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KnowledgeBaseItemModel(Base):
    __tablename__ = "knowledge_base_items"

    source_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(32), index=True)
    item_type: Mapped[str] = mapped_column(String(32), index=True)
    roles: Mapped[list[str]] = mapped_column(JSON_VALUE)
    seniority_levels: Mapped[list[str]] = mapped_column(JSON_VALUE)
    principle: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    interview_signal: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON_VALUE)
    url: Mapped[str | None] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RetrievalEventModel(Base):
    __tablename__ = "retrieval_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="SET NULL"), index=True
    )
    query_sha256: Mapped[str] = mapped_column(String(64))
    selected_source_ids: Mapped[list[str]] = mapped_column(JSON_VALUE)
    scores: Mapped[dict[str, float]] = mapped_column(JSON_VALUE)
    latency_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AgentRunModel(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="SET NULL"), index=True
    )
    workflow: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24))
    model_name: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    error_category: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
