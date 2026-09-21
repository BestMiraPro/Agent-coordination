"""Phase 2 tournament mechanics.

Revision ID: 0002_tournament
Revises: 0001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_tournament"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("max_generations", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "runs",
        sa.Column("population_size", sa.Integer(), server_default="4", nullable=False),
    )
    op.add_column(
        "runs",
        sa.Column("survivor_count", sa.Integer(), server_default="2", nullable=False),
    )
    op.create_check_constraint(
        "ck_run_max_generations_positive",
        "runs",
        "max_generations > 0",
    )
    op.create_check_constraint(
        "ck_run_population_size",
        "runs",
        "population_size > 1",
    )
    op.create_check_constraint(
        "ck_run_survivor_count_positive",
        "runs",
        "survivor_count > 0",
    )
    op.create_check_constraint(
        "ck_run_survivors_lt_population",
        "runs",
        "survivor_count < population_size",
    )

    op.create_table(
        "selection_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column(
            "score_vector",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rank > 0", name="ck_selection_rank_positive"),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "generation_id",
            "submission_id",
            name="uq_selection_generation_submission",
        ),
    )
    op.create_index(
        "ix_selection_decisions_generation_id",
        "selection_decisions",
        ["generation_id"],
        unique=False,
    )
    op.create_index(
        "ix_selection_decisions_submission_id",
        "selection_decisions",
        ["submission_id"],
        unique=False,
    )

    op.create_table(
        "lineage_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mutation_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["child_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_agent_id", name="uq_lineage_child_agent"),
    )
    op.create_index(
        "ix_lineage_links_child_agent_id",
        "lineage_links",
        ["child_agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_lineage_links_parent_submission_id",
        "lineage_links",
        ["parent_submission_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_lineage_links_parent_submission_id", table_name="lineage_links")
    op.drop_index("ix_lineage_links_child_agent_id", table_name="lineage_links")
    op.drop_table("lineage_links")
    op.drop_index("ix_selection_decisions_submission_id", table_name="selection_decisions")
    op.drop_index("ix_selection_decisions_generation_id", table_name="selection_decisions")
    op.drop_table("selection_decisions")
    op.drop_constraint("ck_run_survivors_lt_population", "runs", type_="check")
    op.drop_constraint("ck_run_survivor_count_positive", "runs", type_="check")
    op.drop_constraint("ck_run_population_size", "runs", type_="check")
    op.drop_constraint("ck_run_max_generations_positive", "runs", type_="check")
    op.drop_column("runs", "survivor_count")
    op.drop_column("runs", "population_size")
    op.drop_column("runs", "max_generations")
