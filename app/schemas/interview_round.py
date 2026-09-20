from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.interview_question_template import InterviewQuestionTemplateResponse


class RoundType(str, Enum):
    HR_SCREENING = "HR_SCREENING"
    TECHNICAL = "TECHNICAL"
    PRACTICAL = "PRACTICAL"
    MANAGERIAL = "MANAGERIAL"
    FINAL = "FINAL"
    CUSTOM = "CUSTOM"


class InterviewRoundCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    round_type: RoundType = RoundType.TECHNICAL
    sequence: int = Field(ge=1, default=1)
    description: str | None = None


class InterviewRoundUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    round_type: RoundType | None = None
    sequence: int | None = Field(default=None, ge=1)
    description: str | None = None
    status: str | None = None


class InterviewRoundResponse(BaseModel):
    id: UUID
    job_id: UUID
    name: str
    round_type: str
    sequence: int
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewRoundDetailResponse(InterviewRoundResponse):
    question_templates: list[InterviewQuestionTemplateResponse] = []
