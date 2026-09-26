from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.capability import Capability
    from app.models.job import Job
    from app.models.user import User


class PostHireOutcome(Base):
    __tablename__ = "post_hire_outcomes"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    recorded_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    outcome_period: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="90_DAYS",
    )

    capability_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("capabilities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    capability_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    expected_capability_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    observed_outcome_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    outcome_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    manager_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    evidence_reference: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
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

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="post_hire_outcomes",
    )

    job: Mapped["Job"] = relationship()

    recorder: Mapped["User"] = relationship()

    capability: Mapped["Capability | None"] = relationship()
