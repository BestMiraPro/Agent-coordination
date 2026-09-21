"""Phase 10 engineering workflow.

Revision ID: 0010_engineering
Revises: 0009_control_room
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_engineering"
down_revision: str | None = "0009_control_room"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "engineering_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="CREATED", nullable=False),
        sa.Column("repair_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_repairs", sa.Integer(), server_default="2", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("repair_count >= 0", name="ck_engineering_repair_count"),
        sa.CheckConstraint("max_repairs >= 0", name="ck_engineering_max_repairs"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineering_runs_project_id", "engineering_runs", ["project_id"])

    op.create_table(
        "engineering_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("engineering_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("raw_response", sa.Text(), nullable=False),
        sa.Column("repair_cycle", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["engineering_run_id"], ["engineering_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineering_artifacts_engineering_run_id", "engineering_artifacts", ["engineering_run_id"])

    op.create_table(
        "engineering_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("engineering_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("repair_cycle", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["engineering_run_id"], ["engineering_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineering_checks_engineering_run_id", "engineering_checks", ["engineering_run_id"])

    op.add_column(
        "model_calls",
        sa.Column("engineering_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_model_calls_engineering_run",
        "model_calls",
        "engineering_runs",
        ["engineering_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_model_calls_engineering_run_id", "model_calls", ["engineering_run_id"])


def downgrade() -> None:
    op.drop_index("ix_model_calls_engineering_run_id", table_name="model_calls")
    op.drop_constraint("fk_model_calls_engineering_run", "model_calls", type_="foreignkey")
    op.drop_column("model_calls", "engineering_run_id")
    op.drop_index("ix_engineering_checks_engineering_run_id", table_name="engineering_checks")
    op.drop_table("engineering_checks")
    op.drop_index("ix_engineering_artifacts_engineering_run_id", table_name="engineering_artifacts")
    op.drop_table("engineering_artifacts")
    op.drop_index("ix_engineering_runs_project_id", table_name="engineering_runs")
    op.drop_table("engineering_runs")
