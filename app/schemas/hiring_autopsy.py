from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.post_hire_outcome import PostHireOutcomeResponse


class CapabilityOutcomeComparison(BaseModel):
    capability_name: str
    pre_hire_evidence_state: str = Field(
        ...,
        description="Pre-hire evidence state: DEMONSTRATED, CLAIM, UNKNOWN, VERIFICATION_NEEDED, NOT_EVALUATED.",
    )
    interview_demonstration_state: str = Field(
        ...,
        description="Post-interview demonstration status: DEMONSTRATED_STRONG, INSUFFICIENT, UNTESTED, WEAKNESS.",
    )
    post_hire_outcome_status: str | None = Field(
        default=None,
        description="Observed work outcome: MEETS_EXPECTATION, PARTIALLY_MEETS_EXPECTATION, NEEDS_DEVELOPMENT, INSUFFICIENT_OBSERVATION, or NO_DATA.",
    )
    outcome_delta_observation: str = Field(
        ...,
        description="Neutral, evidence-grounded factual comparison between hiring expectation and observed outcome.",
    )

    model_config = ConfigDict(from_attributes=True)


class AutopsyFinding(BaseModel):
    category: str = Field(
        ...,
        description="Category: UNVERIFIED_CAPABILITY, INTERVIEW_COVERAGE_GAP, OUTCOME_ALIGNMENT, PROCESS_OPPORTUNITY.",
    )
    finding_text: str
    affected_capability: str
    grounded_facts: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AIImprovementSuggestion(BaseModel):
    suggestion_id: str
    affected_capability: str
    observed_pattern: str
    suggested_improvement: str
    action_type: str = Field(
        ...,
        description="Action type: ADD_VERIFICATION_STEP, EXPAND_INTERVIEW_QUESTIONS, UPDATE_CAPABILITY_BLUEPRINT, REFINE_SCREENING_CRITERIA.",
    )
    confidence_strength: str = Field(
        default="HIGH_CONFIDENCE",
        description="Qualitative confidence rating (HIGH_CONFIDENCE, MODERATE_CONFIDENCE, EXPLORATORY).",
    )
    supporting_records: list[str] = Field(default_factory=list)
    is_advisory_only: bool = Field(
        default=True,
        description="AI suggestions are purely advisory. Never automatically modifies hiring rules or candidate states.",
    )

    model_config = ConfigDict(from_attributes=True)


class HiringAutopsyResponse(BaseModel):
    application_id: UUID
    job_id: UUID
    job_title: str
    candidate_id: UUID
    candidate_name: str
    decision_summary: dict[str, Any]
    decision_replay_summary: dict[str, Any]
    post_hire_outcomes: list[PostHireOutcomeResponse] = Field(default_factory=list)
    capability_comparison: list[CapabilityOutcomeComparison] = Field(default_factory=list)
    findings: list[AutopsyFinding] = Field(default_factory=list)
    ai_improvement_suggestions: list[AIImprovementSuggestion] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
