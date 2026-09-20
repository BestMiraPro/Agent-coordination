"""Phase 5 selective cross-pollination.

Revision ID: 0005_cross_pollination
Revises: 0004_memory
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_cross_pollination"
down_revision: str | None = "0004_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cross_pollination_packets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "target_agent_id",
            "source_submission_id",
            name="uq_cross_pollination_target_source",
        ),
    )
    op.create_index("ix_cross_pollination_packets_run_id", "cross_pollination_packets", ["run_id"])
    op.create_index("ix_cross_pollination_packets_generation_id", "cross_pollination_packets", ["generation_id"])
    op.create_index("ix_cross_pollination_packets_target_agent_id", "cross_pollination_packets", ["target_agent_id"])
    op.create_index("ix_cross_pollination_packets_source_submission_id", "cross_pollination_packets", ["source_submission_id"])


def downgrade() -> None:
    op.drop_index("ix_cross_pollination_packets_source_submission_id", table_name="cross_pollination_packets")
    op.drop_index("ix_cross_pollination_packets_target_agent_id", table_name="cross_pollination_packets")
    op.drop_index("ix_cross_pollination_packets_generation_id", table_name="cross_pollination_packets")
    op.drop_index("ix_cross_pollination_packets_run_id", table_name="cross_pollination_packets")
    op.drop_table("cross_pollination_packets")
