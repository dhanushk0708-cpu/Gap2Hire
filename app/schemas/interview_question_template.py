from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionIntent(str, Enum):
    EXPERIENCE = "EXPERIENCE"
    KNOWLEDGE = "KNOWLEDGE"
    DEBUGGING = "DEBUGGING"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    PROBLEM_SOLVING = "PROBLEM_SOLVING"
    BEHAVIORAL = "BEHAVIORAL"
    COMMUNICATION = "COMMUNICATION"
    PRACTICAL = "PRACTICAL"
    FOLLOW_UP = "FOLLOW_UP"
    CLARIFICATION = "CLARIFICATION"


class QuestionDifficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class InterviewQuestionTemplateCreate(BaseModel):
    capability_id: UUID | None = None
    question_intent: QuestionIntent = QuestionIntent.KNOWLEDGE
    question_text: str = Field(min_length=1)
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    required: bool = True
    max_followups: int = Field(ge=0, le=5, default=2)
    sequence: int = Field(ge=1, default=1)


class InterviewQuestionTemplateUpdate(BaseModel):
    capability_id: UUID | None = None
    question_intent: QuestionIntent | None = None
    question_text: str | None = Field(default=None, min_length=1)
    difficulty: QuestionDifficulty | None = None
    required: bool | None = None
    max_followups: int | None = Field(default=None, ge=0, le=5)
    sequence: int | None = Field(default=None, ge=1)


class InterviewQuestionTemplateResponse(BaseModel):
    id: UUID
    round_id: UUID
    capability_id: UUID | None = None
    question_intent: str
    question_text: str
    difficulty: str
    required: bool
    max_followups: int
    sequence: int
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
