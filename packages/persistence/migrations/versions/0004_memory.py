"""Phase 4 persistent research memory.

Revision ID: 0004_memory
Revises: 0003_diversity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_memory"
down_revision: str | None = "0003_diversity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_items_run_id", "knowledge_items", ["run_id"])
    op.create_index("ix_knowledge_items_generation_id", "knowledge_items", ["generation_id"])
    op.create_index("ix_knowledge_items_submission_id", "knowledge_items", ["submission_id"])
    op.create_index("ix_knowledge_items_run_kind", "knowledge_items", ["run_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_items_run_kind", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_submission_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_generation_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_run_id", table_name="knowledge_items")
    op.drop_table("knowledge_items")
