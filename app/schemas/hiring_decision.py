from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HiringDecisionType(str, Enum):
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    ON_HOLD = "ON_HOLD"


class HiringDecisionCreate(BaseModel):
    decision: HiringDecisionType = Field(
        ...,
        description="The human hiring decision: SELECTED, REJECTED, or ON_HOLD.",
    )
    decision_reason: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Required human-entered rationale and evidence justification for the decision.",
    )

    @field_validator("decision_reason")
    @classmethod
    def validate_non_empty_reason(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Decision reason must not be empty or contain only whitespace.")
        if len(trimmed) < 5:
            raise ValueError("Decision reason must be at least 5 characters long.")
        return trimmed


class HiringDecisionResponse(BaseModel):
    id: UUID
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str | None = None
    job_id: UUID
    job_title: str
    decision: str
    decision_reason: str
    decided_by: UUID
    decided_by_name: str
    decided_by_email: str | None = None
    decided_at: datetime
    report_id: UUID | None = None
    previous_decision_id: UUID | None = None
    application_status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HiringDecisionHistoryResponse(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    current_decision: HiringDecisionResponse | None = None
    history: list[HiringDecisionResponse] = Field(default_factory=list)
    total_decisions: int = 0

    model_config = ConfigDict(from_attributes=True)
