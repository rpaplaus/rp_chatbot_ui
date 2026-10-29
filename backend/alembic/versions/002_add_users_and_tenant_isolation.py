"""Add users and tenant isolation

Revision ID: 002_users_tenant
Revises: 001_initial_schema
Create Date: 2026-10-28 17:35:00.000000

"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.core.security import hash_password

# revision identifiers, used by Alembic.
revision: str = "002_users_tenant"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # 2. Seed initial Admin User from .env (APP_USER / APP_PASSWORD)
    admin_id = uuid.uuid4()
    admin_username = (settings.APP_USER or "rpaplaus").strip()
    admin_email = (settings.APP_EMAIL or f"{admin_username}@rpaplaus.com").strip()
    admin_hashed_pw = hash_password(settings.APP_PASSWORD or "Dumai!605Bacon")

    users_table = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String),
        sa.column("username", sa.String),
        sa.column("hashed_password", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("role", sa.String),
    )
    op.bulk_insert(
        users_table,
        [
            {
                "id": admin_id,
                "email": admin_email,
                "username": admin_username,
                "hashed_password": admin_hashed_pw,
                "is_active": True,
                "role": "admin",
            }
        ],
    )

    # 3. Add user_id column to sessions (populate existing rows first, then enforce NOT NULL)
    op.add_column(
        "sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.execute(
        sa.text(f"UPDATE sessions SET user_id = '{admin_id}' WHERE user_id IS NULL")
    )
    op.alter_column("sessions", "user_id", nullable=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_foreign_key(
        "sessions_user_id_fkey",
        "sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("sessions_user_id_fkey", "sessions", type_="foreignkey")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_column("sessions", "user_id")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

