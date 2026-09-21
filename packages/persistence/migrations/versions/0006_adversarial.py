"""Phase 6 adversarial critics and candidate lifecycle.

Revision ID: 0006_adversarial
Revises: 0005_cross_pollination
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_adversarial"
down_revision: str | None = "0005_cross_pollination"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("critic_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_run_critic_nonnegative",
        "runs",
        "critic_count >= 0",
    )

    op.create_table(
        "candidate_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PROPOSED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id", name="uq_candidate_state_submission"),
    )
    op.create_index("ix_candidate_states_generation_id", "candidate_states", ["generation_id"])
    op.create_index("ix_candidate_states_submission_id", "candidate_states", ["submission_id"])

    op.create_table(
        "critic_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("critic_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fatal_error", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("critique", sa.Text(), nullable=False),
        sa.Column("counterexample", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_critic_confidence"),
        sa.ForeignKeyConstraint(["critic_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "critic_agent_id",
            "submission_id",
            name="uq_critic_finding_agent_submission",
        ),
    )
    op.create_index("ix_critic_findings_generation_id", "critic_findings", ["generation_id"])
    op.create_index("ix_critic_findings_critic_agent_id", "critic_findings", ["critic_agent_id"])
    op.create_index("ix_critic_findings_submission_id", "critic_findings", ["submission_id"])


def downgrade() -> None:
    op.drop_index("ix_critic_findings_submission_id", table_name="critic_findings")
    op.drop_index("ix_critic_findings_critic_agent_id", table_name="critic_findings")
    op.drop_index("ix_critic_findings_generation_id", table_name="critic_findings")
    op.drop_table("critic_findings")
    op.drop_index("ix_candidate_states_submission_id", table_name="candidate_states")
    op.drop_index("ix_candidate_states_generation_id", table_name="candidate_states")
    op.drop_table("candidate_states")
    op.drop_constraint("ck_run_critic_nonnegative", "runs", type_="check")
    op.drop_column("runs", "critic_count")
