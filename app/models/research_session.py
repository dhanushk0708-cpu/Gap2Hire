from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.candidate_source import CandidateSource
    from app.models.research_capability import ResearchCapabilityState
    from app.models.research_event import ResearchEvent


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )

    current_source_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("candidate_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    stop_reason: Mapped[Optional[str]] = mapped_column(
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
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    application: Mapped["Application"] = relationship(
        back_populates="research_sessions",
    )

    current_source: Mapped[Optional["CandidateSource"]] = relationship()

    capability_states: Mapped[list["ResearchCapabilityState"]] = relationship(
        back_populates="research_session",
        cascade="all, delete-orphan",
    )

    events: Mapped[list["ResearchEvent"]] = relationship(
        back_populates="research_session",
        cascade="all, delete-orphan",
        order_by="ResearchEvent.created_at.asc()",
    )
