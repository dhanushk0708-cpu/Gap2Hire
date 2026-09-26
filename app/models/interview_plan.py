from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.interview_dataset import InterviewDatasetFile, InterviewDatasetQuestion
    from app.models.job import Job
    from app.models.organization import Organization
    from app.models.user import User


class InterviewPlan(Base):
    __tablename__ = "interview_plans"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
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
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_dataset_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False, index=True)
    candidate_strengths_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_targets_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    hr_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
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

    organization: Mapped["Organization"] = relationship()
    application: Mapped["Application"] = relationship()
    job: Mapped["Job"] = relationship()
    dataset_file: Mapped["InterviewDatasetFile | None"] = relationship()
    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])
    approver: Mapped["User | None"] = relationship(foreign_keys=[approved_by])
    rounds: Mapped[list["InterviewPlanRound"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="InterviewPlanRound.sequence.asc()",
    )


class InterviewPlanRound(Base):
    __tablename__ = "interview_plan_rounds"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    concepts: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    plan: Mapped["InterviewPlan"] = relationship(back_populates="rounds")
    questions: Mapped[list["InterviewPlanQuestion"]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
        order_by="InterviewPlanQuestion.sequence.asc()",
    )


class InterviewPlanQuestion(Base):
    __tablename__ = "interview_plan_questions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    round_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_plan_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_question_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_dataset_questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    concept: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), default="CONCEPTUAL", nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_being_verified: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    round: Mapped["InterviewPlanRound"] = relationship(back_populates="questions")
    dataset_question: Mapped["InterviewDatasetQuestion | None"] = relationship()
