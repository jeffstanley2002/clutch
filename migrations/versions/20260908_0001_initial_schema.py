"""Create the initial privacy-preserving application schema.

Revision ID: 20260908_0001
Revises:
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        )
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "review_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("external_session_id", sa.String(length=120)),
        sa.Column("code_sha256", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("role_context", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("line_count >= 1", name="ck_review_line_count"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_review_confidence",
        ),
    )
    op.create_index(
        "ix_review_sessions_external_session_id",
        "review_sessions",
        ["external_session_id"],
    )
    op.create_index(
        "ix_review_sessions_code_sha256",
        "review_sessions",
        ["code_sha256"],
    )

    op.create_table(
        "review_findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_session_id",
            sa.String(length=36),
            sa.ForeignKey("review_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("finding_id", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("line_start", sa.Integer()),
        sa.Column("line_end", sa.Integer()),
        sa.Column("citation_ids", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_review_findings_review_session_id",
        "review_findings",
        ["review_session_id"],
    )
    op.create_index(
        "ix_review_findings_category",
        "review_findings",
        ["category"],
    )

    op.create_table(
        "generated_questions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_session_id",
            sa.String(length=36),
            sa.ForeignKey("review_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", sa.String(length=120), nullable=False),
        sa.Column("finding_id", sa.String(length=120)),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("citation_ids", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_generated_questions_review_session_id",
        "generated_questions",
        ["review_session_id"],
    )

    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_session_id",
            sa.String(length=36),
            sa.ForeignKey("review_sessions.id", ondelete="SET NULL"),
        ),
        sa.Column("profile_id", sa.String(length=120)),
        sa.Column("role_context", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="active",
            nullable=False,
        ),
        sa.Column("current_question", postgresql.JSONB()),
        sa.Column("remaining_questions", postgresql.JSONB(), nullable=False),
        sa.Column("turn_count", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_interview_sessions_review_session_id",
        "interview_sessions",
        ["review_session_id"],
    )
    op.create_index(
        "ix_interview_sessions_profile_id",
        "interview_sessions",
        ["profile_id"],
    )

    op.create_table(
        "interview_turns",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "interview_session_id",
            sa.String(length=36),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_sha256", sa.String(length=64), nullable=False),
        sa.Column("answer_summary", sa.Text(), nullable=False),
        sa.Column("assessment", postgresql.JSONB(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "interview_session_id",
            "turn_number",
            name="uq_interview_turn_number",
        ),
    )
    op.create_index(
        "ix_interview_turns_interview_session_id",
        "interview_turns",
        ["interview_session_id"],
    )

    op.create_table(
        "progress_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("profile_id", sa.String(length=120), nullable=False),
        sa.Column("time_window", sa.String(length=120), nullable=False),
        sa.Column("improved_areas", postgresql.JSONB(), nullable=False),
        sa.Column("persistent_issues", postgresql.JSONB(), nullable=False),
        sa.Column("next_practice_tasks", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_session_ids", postgresql.JSONB(), nullable=False),
        *_timestamps(),
    )
    op.create_index(
        "ix_progress_snapshots_profile_id",
        "progress_snapshots",
        ["profile_id"],
    )

    op.create_table(
        "knowledge_base_items",
        sa.Column("source_id", sa.String(length=160), primary_key=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("principle", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("interview_signal", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536)),
        *_timestamps(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_knowledge_base_items_category",
        "knowledge_base_items",
        ["category"],
    )
    op.execute(
        "CREATE INDEX ix_knowledge_base_items_search_fts "
        "ON knowledge_base_items USING GIN "
        "(to_tsvector('english', search_text))"
    )
    op.create_index(
        "ix_knowledge_base_items_embedding_hnsw",
        "knowledge_base_items",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "retrieval_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_session_id",
            sa.String(length=36),
            sa.ForeignKey("review_sessions.id", ondelete="SET NULL"),
        ),
        sa.Column("query_sha256", sa.String(length=64), nullable=False),
        sa.Column("selected_source_ids", postgresql.JSONB(), nullable=False),
        sa.Column("scores", postgresql.JSONB(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        *_timestamps(),
    )
    op.create_index(
        "ix_retrieval_events_review_session_id",
        "retrieval_events",
        ["review_session_id"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "review_session_id",
            sa.String(length=36),
            sa.ForeignKey("review_sessions.id", ondelete="SET NULL"),
        ),
        sa.Column("workflow", sa.String(length=80), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("model_name", sa.String(length=120)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Float()),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("error_category", sa.String(length=120)),
        *_timestamps(),
    )
    op.create_index(
        "ix_agent_runs_review_session_id",
        "agent_runs",
        ["review_session_id"],
    )


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("retrieval_events")
    op.drop_table("knowledge_base_items")
    op.drop_table("progress_snapshots")
    op.drop_table("interview_turns")
    op.drop_table("interview_sessions")
    op.drop_table("generated_questions")
    op.drop_table("review_findings")
    op.drop_table("review_sessions")
