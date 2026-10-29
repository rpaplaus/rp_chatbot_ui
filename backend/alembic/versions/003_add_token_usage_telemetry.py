"""Add token_usage telemetry table

Revision ID: 003_token_usage_telemetry
Revises: 002_users_tenant
Create Date: 2026-10-29 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_token_usage_telemetry"
down_revision: Union[str, None] = "002_users_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(precision=14, scale=8), nullable=False, server_default="0.00000000"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_token_usage_id"), "token_usage", ["id"], unique=False)
    op.create_index(op.f("ix_token_usage_user_id"), "token_usage", ["user_id"], unique=False)
    op.create_index(op.f("ix_token_usage_session_id"), "token_usage", ["session_id"], unique=False)
    op.create_index(op.f("ix_token_usage_provider"), "token_usage", ["provider"], unique=False)
    op.create_index(op.f("ix_token_usage_model_name"), "token_usage", ["model_name"], unique=False)
    op.create_index(op.f("ix_token_usage_created_at"), "token_usage", ["created_at"], unique=False)
    op.create_index(
        "ix_token_usage_user_created",
        "token_usage",
        ["user_id", "created_at"],
        unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_token_usage_user_created", table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_created_at"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_model_name"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_provider"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_session_id"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_user_id"), table_name="token_usage")
    op.drop_index(op.f("ix_token_usage_id"), table_name="token_usage")
    op.drop_table("token_usage")

