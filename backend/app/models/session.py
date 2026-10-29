import uuid
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin

class ChatSession(Base, UUIDMixin, TimestampMixin):
    """Represents a conversation session owned by an authenticated user (multi-tenant isolation)."""
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="New Chat",
        nullable=False
    )
    system_prompt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        default="GPT-5 (OpenAI)",
        nullable=False
    )
    web_search_mode: Mapped[str] = mapped_column(
        String(20),
        default="auto",
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions"
    )
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()"
    )
    token_usages: Mapped[List["TokenUsage"]] = relationship(
        "TokenUsage",
        back_populates="session"
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, title='{self.title}', model='{self.model_name}')>"
