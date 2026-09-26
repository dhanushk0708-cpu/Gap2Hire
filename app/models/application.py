from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.candidate_hiring_decision import CandidateHiringDecision
    from app.models.candidate_source import CandidateSource
    from app.models.job import Job
    from app.models.post_hire_outcome import PostHireOutcome
    from app.models.research_session import ResearchSession


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="APPLIED",
    )

    screening_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
    )

    screening_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    shortlist_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
    )

    shortlist_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    shortlisted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_demo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    resume_path: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    resume_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
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

    candidate: Mapped["Candidate"] = relationship(
        back_populates="applications",
    )

    job: Mapped["Job"] = relationship()

    sources: Mapped[list["CandidateSource"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )

    research_sessions: Mapped[list["ResearchSession"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ResearchSession.created_at.asc()",
    )

    hiring_decisions: Mapped[list["CandidateHiringDecision"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="CandidateHiringDecision.decided_at.desc()",
    )

    post_hire_outcomes: Mapped[list["PostHireOutcome"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="PostHireOutcome.recorded_at.desc()",
    )
