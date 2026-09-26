from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.interview_report import InterviewReportModel
    from app.models.job import Job
    from app.models.user import User


class CandidateHiringDecision(Base):
    __tablename__ = "candidate_hiring_decisions"

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

    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    decision_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    decided_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    report_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    previous_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_hiring_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
        back_populates="hiring_decisions",
    )

    job: Mapped["Job"] = relationship()

    decider: Mapped["User"] = relationship()

    report: Mapped["InterviewReportModel | None"] = relationship()

    previous_decision: Mapped["CandidateHiringDecision | None"] = relationship(
        remote_side=[id],
    )
