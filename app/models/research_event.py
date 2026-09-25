from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.candidate_source import CandidateSource
    from app.models.capability import Capability
    from app.models.research_session import ResearchSession


class ResearchEvent(Base):
    __tablename__ = "research_events"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    research_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    source_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("candidate_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    capability_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("capabilities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    research_session: Mapped["ResearchSession"] = relationship(
        back_populates="events",
    )

    source: Mapped[Optional["CandidateSource"]] = relationship()

    capability: Mapped[Optional["Capability"]] = relationship()
