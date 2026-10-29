import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Numeric, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin


class TokenUsage(Base, UUIDMixin):
    """
    Records granular LLM token consumption and calculated USD cost per request.
    Linked to User (CASCADE) and ChatSession (SET NULL to preserve financial audit history
    even if the user deletes the conversation).
    """
    __tablename__ = "token_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 8),
        nullable=False,
        default=Decimal("0.00000000")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="token_usages"
    )
    session: Mapped[Optional["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="token_usages"
    )

    def __repr__(self) -> str:
        return (
            f"<TokenUsage(id={self.id}, user_id={self.user_id}, model='{self.model_name}', "
            f"tokens={self.total_tokens}, cost_usd={self.total_cost})>"
        )

