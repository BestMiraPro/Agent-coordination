"""Phase 8 adaptive resource allocation.

Revision ID: 0008_routing
Revises: 0007_verification
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_routing"
down_revision: str | None = "0007_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "quality_by_task",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("marginal_cash_cost", sa.Float(), server_default="0", nullable=False),
        sa.Column("credit_cost", sa.Float(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Float(), server_default="1000", nullable=False),
        sa.Column("scarcity", sa.Float(), server_default="0", nullable=False),
        sa.Column("failure_rate", sa.Float(), server_default="0", nullable=False),
        sa.Column("rate_limit_pressure", sa.Float(), server_default="0", nullable=False),
        sa.Column("available_concurrency", sa.Integer(), server_default="1", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("failure_rate >= 0 AND failure_rate <= 1", name="ck_model_state_failure"),
        sa.CheckConstraint("rate_limit_pressure >= 0 AND rate_limit_pressure <= 1", name="ck_model_state_rate_pressure"),
        sa.CheckConstraint("scarcity >= 0 AND scarcity <= 1", name="ck_model_state_scarcity"),
        sa.CheckConstraint("available_concurrency >= 0", name="ck_model_state_concurrency"),
        sa.ForeignKeyConstraint(["model_profile_id"], ["model_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_profile_id", name="uq_model_state_profile"),
    )
    op.create_index("ix_model_states_model_profile_id", "model_states", ["model_profile_id"])


def downgrade() -> None:
    op.drop_index("ix_model_states_model_profile_id", table_name="model_states")
    op.drop_table("model_states")
