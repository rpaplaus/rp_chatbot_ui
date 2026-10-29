from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.models.base import Base, UUIDMixin


class SemanticCache(Base, UUIDMixin):
    """
    L2 Vector Cache table backed by PostgreSQL + pgvector (512-d Matryoshka embeddings).
    Stores self-contained question embeddings, profile partition, scope isolation key,
    and dynamic TTL expiration timestamps.
    """
    __tablename__ = "semantic_cache"

    prompt_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    prompt_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    profile_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True
    )
    scope_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="global",
        index=True
    )
    embedding: Mapped[List[float]] = mapped_column(
        Vector(512),
        nullable=False
    )
    response_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    sources_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB,
        nullable=True,
        default=list
    )
    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    def __repr__(self) -> str:
        return (
            f"<SemanticCache(id={self.id}, profile='{self.profile_id}', "
            f"scope='{self.scope_key}', hits={self.hit_count})>"
        )

