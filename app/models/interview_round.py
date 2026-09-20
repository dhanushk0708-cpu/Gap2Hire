from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.capability import Capability
    from app.models.job import Job
    from app.models.user import User


class InterviewRound(Base):
    __tablename__ = "interview_rounds"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_job_round_sequence"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    round_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="TECHNICAL",
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ACTIVE",
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

    job: Mapped["Job"] = relationship()
    question_templates: Mapped[list["InterviewQuestionTemplate"]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
        order_by="InterviewQuestionTemplate.sequence.asc()",
    )


class InterviewQuestionTemplate(Base):
    __tablename__ = "interview_question_templates"
    __table_args__ = (
        UniqueConstraint("round_id", "sequence", name="uq_round_template_sequence"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    round_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    capability_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("capabilities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    question_intent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="KNOWLEDGE",
    )

    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MEDIUM",
    )

    required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    max_followups: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
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

    round: Mapped["InterviewRound"] = relationship(back_populates="question_templates")
    capability: Mapped["Capability | None"] = relationship()
    creator: Mapped["User | None"] = relationship()
