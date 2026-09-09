"""Add knowledge provenance, output origins, and complete model diagnostics.

Revision ID: 20260909_0003
Revises: 20260908_0002
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260909_0003"
down_revision: str | None = "20260908_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_base_items",
        sa.Column("source_family", sa.String(length=64)),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column("source_title", sa.String(length=240)),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column("section_locator", sa.String(length=240)),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column("corpus_version", sa.String(length=64)),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column("content_sha256", sa.String(length=64)),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column(
            "derived_from_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column(
            "is_seeded",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column("embedding_model", sa.String(length=120)),
    )
    op.execute(
        "UPDATE knowledge_base_items SET is_seeded = true "
        "WHERE source_id LIKE 'seed.%'"
    )
    op.create_index(
        "ix_knowledge_base_items_active_type",
        "knowledge_base_items",
        ["is_active", "item_type"],
    )

    op.add_column(
        "review_sessions",
        sa.Column(
            "provenance",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "review_findings",
        sa.Column(
            "origin",
            sa.String(length=40),
            server_default="deterministic_static",
            nullable=False,
        ),
    )
    op.add_column(
        "generated_questions",
        sa.Column(
            "origin",
            sa.String(length=40),
            server_default="template_generated",
            nullable=False,
        ),
    )
    op.add_column(
        "interview_turns",
        sa.Column(
            "assessment_origin",
            sa.String(length=40),
            server_default="deterministic_static",
            nullable=False,
        ),
    )

    op.alter_column(
        "agent_runs",
        "error_category",
        new_column_name="failure_category",
    )
    op.add_column("agent_runs", sa.Column("prompt_version", sa.String(length=64)))
    op.add_column(
        "agent_runs",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "validation_failure_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "validation_failure_count")
    op.drop_column("agent_runs", "attempt_count")
    op.drop_column("agent_runs", "prompt_version")
    op.alter_column(
        "agent_runs",
        "failure_category",
        new_column_name="error_category",
    )
    op.drop_column("interview_turns", "assessment_origin")
    op.drop_column("generated_questions", "origin")
    op.drop_column("review_findings", "origin")
    op.drop_column("review_sessions", "provenance")
    op.drop_index(
        "ix_knowledge_base_items_active_type",
        table_name="knowledge_base_items",
    )
    op.drop_column("knowledge_base_items", "embedding_model")
    op.drop_column("knowledge_base_items", "is_seeded")
    op.drop_column("knowledge_base_items", "is_active")
    op.drop_column("knowledge_base_items", "derived_from_ids")
    op.drop_column("knowledge_base_items", "content_sha256")
    op.drop_column("knowledge_base_items", "corpus_version")
    op.drop_column("knowledge_base_items", "section_locator")
    op.drop_column("knowledge_base_items", "source_title")
    op.drop_column("knowledge_base_items", "source_family")
