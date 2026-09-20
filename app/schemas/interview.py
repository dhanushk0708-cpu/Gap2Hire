from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InterviewSessionStatus(str, Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InterviewRole(str, Enum):
    SYSTEM = "SYSTEM"
    AI = "AI"
    CANDIDATE = "CANDIDATE"


class InterviewSessionCreate(BaseModel):
    pass


class InterviewQuestionResponse(BaseModel):
    id: UUID
    session_id: UUID
    capability_id: UUID
    question: str
    answer: str | None = None
    sequence_number: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: InterviewRole
    content: str
    sequence_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewSessionResponse(BaseModel):
    id: UUID
    application_id: UUID
    status: InterviewSessionStatus
    current_capability_id: UUID | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewSessionDetailResponse(InterviewSessionResponse):
    questions: list[InterviewQuestionResponse] = []
    messages: list[InterviewMessageResponse] = []


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)


class AIQuestionPayload(BaseModel):
    question: str = Field(min_length=1)
    target_capability: str = Field(min_length=1)
    reason: str = Field(min_length=1)
