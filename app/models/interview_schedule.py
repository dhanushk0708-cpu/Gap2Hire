from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.interview import InterviewSession
    from app.models.organization import Organization
    from app.models.user import User


class InterviewSchedule(Base):
    __tablename__ = "interview_schedules"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scheduled_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    scheduled_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="UTC",
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=45,
    )

    calendar_event_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    meeting_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SCHEDULED",
        index=True,
    )

    candidate_email_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    candidate_email_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    invitation_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
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

    session: Mapped["InterviewSession"] = relationship()
    application: Mapped["Application"] = relationship()
    organization: Mapped["Organization"] = relationship()
    creator: Mapped["User | None"] = relationship()
