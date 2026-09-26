from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.capability import Capability
    from app.models.interview_integrity import InterviewIntegrityEvent
    from app.models.interview_report import InterviewReportModel
    from app.models.interview_round import InterviewRound


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

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
        nullable=False,
        default="CREATED",
        index=True,
    )

    current_round_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_rounds.id", ondelete="SET NULL"),
        nullable=True,
    )

    current_capability_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("capabilities.id", ondelete="SET NULL"),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
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

    application: Mapped["Application"] = relationship()
    current_round: Mapped["InterviewRound | None"] = relationship()
    current_capability: Mapped["Capability | None"] = relationship()
    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.sequence_number.asc()",
    )
    answer_analyses: Mapped[list["InterviewAnswerAnalysis"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewMessage.sequence_number.asc()",
    )
    integrity_events: Mapped[list["InterviewIntegrityEvent"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewIntegrityEvent.occurred_at.asc()",
    )
    report: Mapped["InterviewReportModel | None"] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    capability_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("capabilities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    plan_question_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_plan_questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    parent_question_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    question_type: Mapped[str] = mapped_column(
        String(50),
        default="PLANNED",
        nullable=False,
    )

    concept: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    answer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
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

    session: Mapped["InterviewSession"] = relationship(back_populates="questions")
    capability: Mapped["Capability | None"] = relationship()
    parent_question: Mapped["InterviewQuestion | None"] = relationship(remote_side=[id])


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    session: Mapped["InterviewSession"] = relationship(back_populates="messages")
