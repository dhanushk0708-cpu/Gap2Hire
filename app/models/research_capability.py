from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.capability import Capability
    from app.models.research_session import ResearchSession


class ResearchCapabilityState(Base):
    __tablename__ = "research_capability_states"
    __table_args__ = (
        UniqueConstraint(
            "research_session_id",
            "capability_id",
            name="uq_research_session_capability",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    research_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    capability_id: Mapped[UUID] = mapped_column(
        ForeignKey("capabilities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    state: Mapped[str] = mapped_column(
        String(50),
        default="UNKNOWN",
        nullable=False,
        index=True,
    )

    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    research_session: Mapped["ResearchSession"] = relationship(
        back_populates="capability_states",
    )

    capability: Mapped["Capability"] = relationship()
