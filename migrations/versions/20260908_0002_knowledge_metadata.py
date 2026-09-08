"""Add role and item-type metadata to knowledge-base records.

Revision ID: 20260908_0002
Revises: 20260908_0001
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0002"
down_revision: str | None = "20260908_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_base_items",
        sa.Column(
            "item_type",
            sa.String(length=32),
            server_default="reference",
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column(
            "roles",
            postgresql.JSONB(),
            server_default=sa.text("'[\"general\"]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_base_items",
        sa.Column(
            "seniority_levels",
            postgresql.JSONB(),
            server_default=sa.text('\'["intern", "junior"]\'::jsonb'),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_knowledge_base_items_item_type",
        "knowledge_base_items",
        ["item_type"],
    )
    op.alter_column(
        "knowledge_base_items",
        "item_type",
        server_default=None,
    )
    op.alter_column(
        "knowledge_base_items",
        "roles",
        server_default=None,
    )
    op.alter_column(
        "knowledge_base_items",
        "seniority_levels",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_base_items_item_type",
        table_name="knowledge_base_items",
    )
    op.drop_column("knowledge_base_items", "seniority_levels")
    op.drop_column("knowledge_base_items", "roles")
    op.drop_column("knowledge_base_items", "item_type")
