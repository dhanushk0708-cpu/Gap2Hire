from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.organization import Organization
    from app.models.user import User


class InterviewDatasetFile(Base):
    __tablename__ = "interview_dataset_files"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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

    organization: Mapped["Organization"] = relationship()
    job: Mapped["Job | None"] = relationship()
    creator: Mapped["User | None"] = relationship()
    datasets: Mapped[list["InterviewQuestionDataset"]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="InterviewQuestionDataset.created_at.asc()",
    )


class InterviewQuestionDataset(Base):
    __tablename__ = "interview_question_datasets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_dataset_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    concept: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    file: Mapped["InterviewDatasetFile"] = relationship(back_populates="datasets")
    questions: Mapped[list["InterviewDatasetQuestion"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="InterviewDatasetQuestion.created_at.asc()",
    )


class InterviewDatasetQuestion(Base):
    __tablename__ = "interview_dataset_questions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_question_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    concept: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), default="CONCEPTUAL", nullable=False)
    expected_topics: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    dataset: Mapped["InterviewQuestionDataset"] = relationship(back_populates="questions")
