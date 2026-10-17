from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pre_interview_scorecard import (
    ConfidenceLevelEnum,
    PreInterviewCapabilityStatusEnum,
    ScorecardEvidenceItem,
    ScorecardVerificationRecommendation,
)


class PostInterviewChangeTypeEnum(str, Enum):
    STRENGTHENED = "STRENGTHENED"
    CONFIRMED = "CONFIRMED"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"
    REMAINED_UNKNOWN = "REMAINED_UNKNOWN"
    CONTRADICTORY = "CONTRADICTORY"


class InterviewEvidenceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    question_id: str | None = None
    question_text: str
    candidate_answer_excerpt: str | None = None
    evaluation_summary: str | None = None
    evaluation_quality: str | None = None  # SUFFICIENT, PARTIAL, INSUFFICIENT, UNANSWERED
    source_timestamp: str | None = None
    limitations: str | None = None


class PostInterviewCapabilityScorecardItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    capability_id: UUID
    capability_name: str
    requirement_description: str | None = None
    importance: str | None = None

    # A. Pre-Interview Baseline (Frozen historical snapshot)
    original_status: PreInterviewCapabilityStatusEnum
    original_confidence: ConfidenceLevelEnum
    original_rationale: str
    original_evidence: list[ScorecardEvidenceItem] = Field(default_factory=list)
    original_verification_guidance: str | None = None

    # B. Post-Interview Updated Assessment
    updated_status: PreInterviewCapabilityStatusEnum
    updated_confidence: ConfidenceLevelEnum
    updated_rationale: str
    interview_evidence: list[InterviewEvidenceItem] = Field(default_factory=list)
    remaining_uncertainties: str | None = None
    recommended_follow_up: ScorecardVerificationRecommendation | None = None

    # C. Change Analysis
    change_type: PostInterviewChangeTypeEnum
    change_summary: str


class PostInterviewScorecard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: UUID
    job_id: UUID
    job_title: str
    candidate_id: UUID
    candidate_name: str
    interview_session_id: UUID
    assessment_timestamp: datetime
    scorecard_version: int

    # Baseline link
    baseline_scorecard_id: UUID
    baseline_assessment_timestamp: datetime

    # Metric comparison
    baseline_readiness_score: float
    post_interview_readiness_score: float
    readiness_change_delta: float
    score_explanation: str
    executive_summary: str

    total_capabilities: int
    supported_count: int
    partial_count: int
    unknown_count: int
    contradictory_count: int
    capabilities_strengthened_count: int
    capabilities_unverified_count: int
    critical_verification_needs: list[str] = Field(default_factory=list)
    human_review_notice: str

    capabilities: list[PostInterviewCapabilityScorecardItem] = Field(default_factory=list)
