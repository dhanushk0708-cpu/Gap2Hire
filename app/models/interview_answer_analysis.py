from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.interview import InterviewSession, InterviewQuestion

class InterviewAnswerAnalysis(Base):
    __tablename__ = "interview_answer_analyses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    session: Mapped["InterviewSession"] = relationship(back_populates="answer_analyses")
    question: Mapped["InterviewQuestion"] = relationship()
