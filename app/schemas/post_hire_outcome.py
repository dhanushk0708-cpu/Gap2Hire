from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutcomeStatus(str, Enum):
    MEETS_EXPECTATION = "MEETS_EXPECTATION"
    PARTIALLY_MEETS_EXPECTATION = "PARTIALLY_MEETS_EXPECTATION"
    NEEDS_DEVELOPMENT = "NEEDS_DEVELOPMENT"
    INSUFFICIENT_OBSERVATION = "INSUFFICIENT_OBSERVATION"


class OutcomePeriod(str, Enum):
    PERIOD_30_DAYS = "30_DAYS"
    PERIOD_60_DAYS = "60_DAYS"
    PERIOD_90_DAYS = "90_DAYS"
    PROBATION = "PROBATION"
    FIRST_QUARTER = "FIRST_QUARTER"
    ANNUAL = "ANNUAL"


class PostHireOutcomeCreate(BaseModel):
    capability_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="The technical or domain capability evaluated during work execution.",
    )
    capability_id: UUID | None = None
    outcome_period: str = Field(
        default="90_DAYS",
        description="Observation window (e.g., 30_DAYS, 60_DAYS, 90_DAYS, PROBATION).",
    )
    expected_capability_description: str | None = Field(
        default=None,
        description="Context on what was expected based on hiring requirements/resume claims.",
    )
    observed_outcome_description: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Factual, objective description of observed job performance for this capability.",
    )
    outcome_status: OutcomeStatus = Field(
        ...,
        description="Controlled outcome rating (MEETS_EXPECTATION, PARTIALLY_MEETS_EXPECTATION, NEEDS_DEVELOPMENT, INSUFFICIENT_OBSERVATION).",
    )
    manager_notes: str | None = Field(
        default=None,
        description="Optional internal manager observations or context.",
    )
    evidence_reference: str | None = Field(
        default=None,
        max_length=512,
        description="Optional reference link, PR, commit, or project doc.",
    )

    @field_validator("observed_outcome_description")
    @classmethod
    def validate_non_empty_description(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 5:
            raise ValueError("Observed outcome description must be at least 5 characters.")
        return trimmed


class PostHireOutcomeResponse(BaseModel):
    id: UUID
    application_id: UUID
    job_id: UUID
    job_title: str
    candidate_id: UUID
    candidate_name: str
    recorded_by: UUID
    recorded_by_name: str
    recorded_at: datetime
    outcome_period: str
    capability_id: UUID | None = None
    capability_name: str
    expected_capability_description: str | None = None
    observed_outcome_description: str
    outcome_status: str
    manager_notes: str | None = None
    evidence_reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostHireOutcomeListResponse(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    outcomes: list[PostHireOutcomeResponse] = Field(default_factory=list)
    total_outcomes: int = 0

    model_config = ConfigDict(from_attributes=True)
