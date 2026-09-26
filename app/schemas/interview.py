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
    capability_id: UUID | None = None
    plan_question_id: UUID | None = None
    parent_question_id: UUID | None = None
    question_type: str = "PLANNED"
    concept: str | None = None
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


class AnswerQualityEnum(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceStateEnum(str, Enum):
    DEMONSTRATED = "DEMONSTRATED"
    VERIFICATION_NEEDED = "VERIFICATION_NEEDED"
    UNKNOWN = "UNKNOWN"


class InterviewActionEnum(str, Enum):
    NEXT_QUESTION = "NEXT_QUESTION"
    FOLLOW_UP = "FOLLOW_UP"
    ROUND_COMPLETE = "ROUND_COMPLETE"


class InterviewAnswerAnalysisSchema(BaseModel):
    answer_quality: str
    evidence_state: str
    key_findings: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    follow_up_needed: bool = False
    follow_up_reason: str = ""


class NextQuestionPayload(BaseModel):
    id: UUID | None = None
    question: str
    concept: str | None = None
    question_type: str = "PLANNED"
    sequence_number: int | None = None
    plan_question_id: UUID | None = None
    parent_question_id: UUID | None = None
    round_number: int | None = None
    round_title: str | None = None


class InterviewAnswerSubmissionResponse(BaseModel):
    analysis: InterviewAnswerAnalysisSchema
    action: str
    next_question: NextQuestionPayload | None = None
    question_id: UUID | None = None
    answer: str | None = None
    round_number: int | None = None
    round_title: str | None = None
    round_status: str | None = None
    interview_status: str | None = None


class InterviewRoundState(BaseModel):
    round_number: int
    title: str
    objective: str | None = None
    round_id: UUID | None = None
    status: str = "IN_PROGRESS"
    total_questions: int = 0
    questions_completed: int = 0


class InterviewExecutionStateResponse(BaseModel):
    session_id: UUID
    interview_status: str
    current_round: dict | None = None
    current_question: str | None = None
    current_question_type: str | None = None
    round_status: str
    questions_completed: int = 0
    total_planned_questions: int = 0
    follow_up_count: int = 0
    total_rounds: int = 0
    rounds: list[dict] = Field(default_factory=list)
