from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InterviewPlanQuestionSchema(BaseModel):
    id: UUID | None = None
    dataset_question_id: UUID | None = None
    question_text: str
    concept: str
    difficulty: str = "MEDIUM"
    question_type: str = "CONCEPTUAL"
    purpose: str | None = None
    evidence_being_verified: str | None = None
    is_hr_authored: bool = False
    status: str = "APPROVED"
    sequence: int = 1

    model_config = ConfigDict(from_attributes=True)


class InterviewPlanRoundSchema(BaseModel):
    id: UUID | None = None
    round_number: int
    title: str
    objective: str
    description: str | None = None
    concepts: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)
    expected_evidence: list[str] = Field(default_factory=list)
    question_generation_mode: str = "AI_GENERATED"  # AI_GENERATED, HR_DEFINED, HYBRID
    difficulty: str = "MEDIUM"
    estimated_duration_minutes: int = 30
    required: bool = True
    reasoning: str | None = None
    sequence: int = 1
    questions: list[InterviewPlanQuestionSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InterviewPlanResponse(BaseModel):
    id: UUID
    application_id: UUID
    job_id: UUID
    dataset_file_id: UUID | None = None
    version: int = 1
    lock_version: int = 1
    status: str = "DRAFT"  # DRAFT, APPROVED, SUPERSEDED, REJECTED
    candidate_strengths_summary: str | None = None
    verification_targets_summary: str | None = None
    hr_feedback: str | None = None
    created_by: UUID | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    rounds: list[InterviewPlanRoundSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InterviewPlanCreateRequest(BaseModel):
    dataset_file_id: UUID | None = None


class InterviewPlanUpdateRequest(BaseModel):
    rounds: list[InterviewPlanRoundSchema]
    hr_feedback: str | None = None
    lock_version: int | None = None  # Optimistic concurrency lock


class InterviewPlanApprovalRequest(BaseModel):
    notes: str | None = None


class RoundQuestionGeneratePreviewRequest(BaseModel):
    round_title: str
    objective: str
    description: str | None = None
    concepts: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)
    expected_evidence: list[str] = Field(default_factory=list)
    difficulty: str = "MEDIUM"
    duration_minutes: int = 30
    question_generation_mode: str = "AI_GENERATED"  # AI_GENERATED, HR_DEFINED, HYBRID
    hr_questions: list[InterviewPlanQuestionSchema] = Field(default_factory=list)
    target_count: int = 3


class RoundReorderRequest(BaseModel):
    round_ids: list[UUID]
