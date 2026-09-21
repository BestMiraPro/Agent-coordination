"""Phase 9 control-room projects and dashboard support.

Revision ID: 0009_control_room
Revises: 0008_routing
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_control_room"
down_revision: str | None = "0008_routing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "problems",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_problems_project",
        "problems",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_problems_project_id", "problems", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_problems_project_id", table_name="problems")
    op.drop_constraint("fk_problems_project", "problems", type_="foreignkey")
    op.drop_column("problems", "project_id")
    op.drop_table("projects")
