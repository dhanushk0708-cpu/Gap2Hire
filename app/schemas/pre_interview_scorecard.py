from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PreInterviewCapabilityStatusEnum(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    CONTRADICTORY = "CONTRADICTORY"


class ConfidenceLevelEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class ScorecardEvidenceItem(BaseModel):
    id: str | None = None
    source_type: str = "RESUME"
    source_reference: str | None = None
    excerpt: str = ""
    source_location: str | None = None
    provenance: str = "CLAIM"
    strength: str = "MODERATE"
    created_at: str | None = None
    limitations: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ScorecardVerificationRecommendation(BaseModel):
    action_type: str = "INTERVIEW_PROBE"
    priority: str = "MEDIUM"
    guidance: str = ""


class TargetedInterviewQuestion(BaseModel):
    question_text: str
    intent: str = "VERIFY_CLAIM"
    difficulty: str = "MID"
    expected_signals: str = ""
    source: str = "Analytical Verification Engine"


class CapabilityScorecardItem(BaseModel):
    capability_id: str | UUID
    capability_name: str
    requirement_description: str | None = None
    importance: str = "MEDIUM"
    status: PreInterviewCapabilityStatusEnum
    status_rationale: str
    confidence: ConfidenceLevelEnum
    confidence_justification: str
    supporting_evidence: list[ScorecardEvidenceItem] = Field(default_factory=list)
    recommended_verification: ScorecardVerificationRecommendation
    targeted_questions: list[TargetedInterviewQuestion] = Field(default_factory=list)


class PreInterviewScorecard(BaseModel):
    application_id: UUID
    job_id: UUID
    job_title: str
    job_description: str | None = None
    candidate_id: UUID
    candidate_name: str
    candidate_email: str | None = None
    assessment_timestamp: datetime = Field(default_factory=datetime.utcnow)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1

    # Capability assessments
    capabilities: list[CapabilityScorecardItem] = Field(default_factory=list)

    # Summary metrics
    total_capabilities: int = 0
    supported_count: int = 0
    partial_count: int = 0
    unknown_count: int = 0
    contradictory_count: int = 0
    critical_verification_needs: list[str] = Field(default_factory=list)

    # Evidence completeness index
    evidence_readiness_score: float = 0.0
    score_explanation: str = (
        "The Evidence Readiness Score measures the proportion of required capabilities with documented "
        "or verified evidence in the candidate's artifacts. It is an index of evidence completeness, "
        "NOT a prediction of job success or a recommendation to hire or reject."
    )

    # Narrative synthesis
    executive_summary: str = ""
    human_review_notice: str = (
        "NOTICE FOR EVALUATORS: Absence of evidence is not evidence of absence. An 'UNKNOWN' assessment "
        "indicates that the candidate's submitted artifacts did not contain explicit mention of the capability, "
        "NOT that the candidate lacks proficiency. All hiring decisions must be made by human reviewers."
    )

    model_config = ConfigDict(from_attributes=True)
