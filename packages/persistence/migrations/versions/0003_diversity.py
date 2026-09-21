"""Phase 3 diversity preservation.

Revision ID: 0003_diversity
Revises: 0002_tournament
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_diversity"
down_revision: str | None = "0002_tournament"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("fresh_agent_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "runs",
        sa.Column(
            "redundancy_threshold",
            sa.Float(),
            server_default="0.78",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_run_fresh_nonnegative",
        "runs",
        "fresh_agent_count >= 0",
    )
    op.create_check_constraint(
        "ck_run_fresh_lt_population",
        "runs",
        "fresh_agent_count < population_size",
    )
    op.create_check_constraint(
        "ck_run_redundancy_threshold",
        "runs",
        "redundancy_threshold >= 0 AND redundancy_threshold <= 1",
    )

    op.add_column(
        "agents",
        sa.Column("niche", sa.String(length=64), server_default="CONSTRUCTIVE", nullable=False),
    )
    op.add_column(
        "agents",
        sa.Column("origin", sa.String(length=32), server_default="INITIAL", nullable=False),
    )

    op.add_column(
        "selection_decisions",
        sa.Column(
            "selection_kind",
            sa.String(length=32),
            server_default="ELIMINATED",
            nullable=False,
        ),
    )
    op.add_column(
        "selection_decisions",
        sa.Column("novelty_score", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "selection_decisions",
        sa.Column(
            "redundant_with_submission_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_selection_novelty_score",
        "selection_decisions",
        "novelty_score >= 0 AND novelty_score <= 1",
    )
    op.create_foreign_key(
        "fk_selection_redundant_submission",
        "selection_decisions",
        "submissions",
        ["redundant_with_submission_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_selection_decisions_redundant_with_submission_id",
        "selection_decisions",
        ["redundant_with_submission_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_selection_decisions_redundant_with_submission_id",
        table_name="selection_decisions",
    )
    op.drop_constraint(
        "fk_selection_redundant_submission",
        "selection_decisions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_selection_novelty_score",
        "selection_decisions",
        type_="check",
    )
    op.drop_column("selection_decisions", "redundant_with_submission_id")
    op.drop_column("selection_decisions", "novelty_score")
    op.drop_column("selection_decisions", "selection_kind")
    op.drop_column("agents", "origin")
    op.drop_column("agents", "niche")
    op.drop_constraint("ck_run_redundancy_threshold", "runs", type_="check")
    op.drop_constraint("ck_run_fresh_lt_population", "runs", type_="check")
    op.drop_constraint("ck_run_fresh_nonnegative", "runs", type_="check")
    op.drop_column("runs", "redundancy_threshold")
    op.drop_column("runs", "fresh_agent_count")
