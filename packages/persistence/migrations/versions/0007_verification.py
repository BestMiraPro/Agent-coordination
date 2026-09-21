"""Phase 7 deterministic verification framework.

Revision ID: 0007_verification
Revises: 0006_adversarial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_verification"
down_revision: str | None = "0006_adversarial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column(
            "verification_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "verification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="INCONCLUSIVE", nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submission_id",
            "kind",
            name="uq_verification_submission_kind",
        ),
    )
    op.create_index("ix_verification_results_run_id", "verification_results", ["run_id"])
    op.create_index("ix_verification_results_generation_id", "verification_results", ["generation_id"])
    op.create_index("ix_verification_results_submission_id", "verification_results", ["submission_id"])


def downgrade() -> None:
    op.drop_index("ix_verification_results_submission_id", table_name="verification_results")
    op.drop_index("ix_verification_results_generation_id", table_name="verification_results")
    op.drop_index("ix_verification_results_run_id", table_name="verification_results")
    op.drop_table("verification_results")
    op.drop_column("runs", "verification_enabled")
