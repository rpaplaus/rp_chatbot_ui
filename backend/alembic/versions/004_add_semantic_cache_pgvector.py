"""Add semantic_cache table with pgvector and HNSW index

Revision ID: 004_semantic_cache_pgvector
Revises: 003_token_usage_telemetry
Create Date: 2026-10-29 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "004_semantic_cache_pgvector"
down_revision: Union[str, None] = "003_token_usage_telemetry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension in PostgreSQL 16
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create semantic_cache table
    op.create_table(
        "semantic_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("profile_id", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=False, server_default="global"),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("sources_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. Create B-Tree and HNSW Vector Indexes
    op.create_index(op.f("ix_semantic_cache_id"), "semantic_cache", ["id"], unique=False)
    op.create_index(op.f("ix_semantic_cache_prompt_hash"), "semantic_cache", ["prompt_hash"], unique=False)
    op.create_index(op.f("ix_semantic_cache_profile_id"), "semantic_cache", ["profile_id"], unique=False)
    op.create_index(op.f("ix_semantic_cache_scope_key"), "semantic_cache", ["scope_key"], unique=False)
    op.create_index(op.f("ix_semantic_cache_created_at"), "semantic_cache", ["created_at"], unique=False)
    op.create_index(op.f("ix_semantic_cache_expires_at"), "semantic_cache", ["expires_at"], unique=False)
    op.create_index(
        "ix_semantic_cache_profile_scope_exp",
        "semantic_cache",
        ["profile_id", "scope_key", "expires_at"],
        unique=False
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_semantic_cache_embedding_hnsw "
        "ON semantic_cache USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_semantic_cache_embedding_hnsw")
    op.drop_index("ix_semantic_cache_profile_scope_exp", table_name="semantic_cache")
    op.drop_index(op.f("ix_semantic_cache_expires_at"), table_name="semantic_cache")
    op.drop_index(op.f("ix_semantic_cache_created_at"), table_name="semantic_cache")
    op.drop_index(op.f("ix_semantic_cache_scope_key"), table_name="semantic_cache")
    op.drop_index(op.f("ix_semantic_cache_profile_id"), table_name="semantic_cache")
    op.drop_index(op.f("ix_semantic_cache_prompt_hash"), table_name="semantic_cache")
    op.drop_index(op.f("ix_semantic_cache_id"), table_name="semantic_cache")
    op.drop_table("semantic_cache")

