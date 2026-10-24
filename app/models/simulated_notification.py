from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.interview_schedule import InterviewSchedule
    from app.models.organization import Organization


class SimulatedNotification(Base):
    __tablename__ = "simulated_notifications"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    interview_schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_schedules.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    recipient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    recipient_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    interview_reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    notification_type: Mapped[str] = mapped_column(
        String(50),  # INVITATION, RESCHEDULE, CANCELLATION, BOOKING_CONFIRMATION, REMINDER
        nullable=False,
        index=True,
    )

    delivery_mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="DEMO_SIMULATED",
    )

    delivery_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="DELIVERED",
    )

    demo_banner: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="DEMO MODE — EMAILS NOT SENT",
    )

    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship()
    schedule: Mapped["InterviewSchedule | None"] = relationship(
        back_populates="notifications",
    )
