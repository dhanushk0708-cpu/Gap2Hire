from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.interview_schedule import InterviewSchedule
    from app.models.organization import Organization
    from app.models.user import User


class InterviewBookingSlot(Base):
    __tablename__ = "interview_booking_slots"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
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

    interviewer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=45,
    )

    interview_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ONLINE",
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    booking_token: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    is_booked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    booked_schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_schedules.id", ondelete="SET NULL"),
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

    organization: Mapped["Organization"] = relationship()
    application: Mapped["Application"] = relationship()
    interviewer: Mapped["User"] = relationship(foreign_keys=[interviewer_id])
    booked_schedule: Mapped["InterviewSchedule | None"] = relationship()
