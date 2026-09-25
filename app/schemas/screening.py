from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequirementEvaluation(BaseModel):
    requirement_name: str
    requirement_type: str = "CAPABILITY"  # "EXPERIENCE", "CAPABILITY", "QUALIFICATION", "CUSTOM"
    status: str = "NEEDS_REVIEW"  # "MET", "NOT_MET", "UNKNOWN", "NEEDS_REVIEW", "INSUFFICIENT"
    evidence_found: str | None = None
    provenance: str | None = "CLAIM"  # "CLAIM", "DEMONSTRATED", "VERIFIED", "UNKNOWN"
    strength: str | None = None  # "STRONG", "MODERATE", "WEAK", "INSUFFICIENT"
    reason: str = ""
    source_type: str | None = None  # "RESUME", "GITHUB", "VERIFICATION", etc.
    source_url: str | None = None
    verification_needed: bool = False
    verification_status: str = "NOT_YET_VERIFIED"  # "NOT_YET_VERIFIED", "PENDING", "PASSED"
    next_step: str = "Practical verification"


class CandidateScreeningResult(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    job_id: UUID
    job_title: str
    eligibility_status: str = "NEEDS_REVIEW"  # "ELIGIBLE", "NOT_ELIGIBLE", "NEEDS_REVIEW"
    screening_status: str = "SCREENING"
    shortlist_status: str = "PENDING"
    shortlist_reason: str | None = None
    requirements_evaluated: list[RequirementEvaluation] = Field(default_factory=list)
    claims_summary: list[str] = Field(default_factory=list)
    unknowns_summary: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    summary_explanation: str = ""
    verified_count: int = 0
    demonstrated_count: int = 0
    claims_count: int = 0
    unknown_count: int = 0
    insufficient_count: int = 0
    verification_needed_count: int = 0
    supported_count: int = 0
    total_requirements_count: int = 0
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class ScreeningUpdateRequest(BaseModel):
    screening_status: str
    screening_notes: str | None = None


class ShortlistDecisionRequest(BaseModel):
    decision: str  # "SHORTLISTED", "NOT_SHORTLISTED", "HOLD"
    reason: str | None = None


class ShortlistDecisionResponse(BaseModel):
    application_id: UUID
    status: str
    screening_status: str
    shortlist_status: str
    shortlist_reason: str | None = None
    shortlisted_at: datetime | None = None
    is_interview_ready: bool = False

    model_config = ConfigDict(from_attributes=True)


class JobCandidateListItem(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    status: str
    screening_status: str
    shortlist_status: str
    shortlist_reason: str | None = None
    applied_at: datetime
    has_resume: bool
    is_interview_ready: bool
    is_demo: bool = False

    model_config = ConfigDict(from_attributes=True)


class ShortlistSizeUpdateRequest(BaseModel):
    shortlist_size: int = Field(ge=1, le=1000)


class CapabilityScreeningEvaluation(BaseModel):
    capability_id: UUID
    capability_name: str
    importance: str = "MEDIUM"  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    is_required: bool = False
    status: str = "NEEDS_REVIEW"  # "MET", "NOT_MET", "UNKNOWN", "INSUFFICIENT", "NEEDS_REVIEW"
    evidence_ids: list[UUID] = Field(default_factory=list)
    evidence_strength: str | None = None  # "STRONG", "MODERATE", "WEAK", "INSUFFICIENT"
    provenance: str | None = "CLAIM"  # "DEMONSTRATED", "CORROBORATED", "CLAIM", "UNKNOWN"
    content: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    unknown_reason: str | None = None
    verification_needed: bool = False

    model_config = ConfigDict(from_attributes=True)


class CandidateScreeningProfile(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    job_id: UUID
    job_title: str
    screening_status: str = "SCREENING"
    shortlist_status: str = "PENDING"
    rank: int | None = None
    capability_results: list[CapabilityScreeningEvaluation] = Field(default_factory=list)
    hard_requirement_coverage: dict[str, Any] = Field(default_factory=dict)
    required_capability_evidence: list[dict[str, Any]] = Field(default_factory=list)
    preferred_capability_evidence: list[dict[str, Any]] = Field(default_factory=list)
    evidence_strength: dict[str, int] = Field(default_factory=dict)
    evidence_provenance: dict[str, int] = Field(default_factory=dict)
    relevant_project_evidence: list[str] = Field(default_factory=list)
    relevant_resume_evidence: list[str] = Field(default_factory=list)
    unknown_capabilities: list[str] = Field(default_factory=list)
    insufficient_capabilities: list[str] = Field(default_factory=list)
    verification_needed: list[str] = Field(default_factory=list)
    summary_explanation: str = ""
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class TopNCandidateItem(BaseModel):
    rank: int
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    shortlist_status: str
    hard_requirements_met: int
    total_hard_requirements: int
    preferred_requirements_met: int
    demonstrated_evidence_count: int
    strong_evidence_count: int
    unknown_count: int
    summary_explanation: str
    selection_reason: str

    model_config = ConfigDict(from_attributes=True)


class JobTopNResult(BaseModel):
    job_id: UUID
    job_title: str
    shortlist_size: int
    total_candidates_evaluated: int
    top_n_candidates: list[TopNCandidateItem] = Field(default_factory=list)
    cutoff_candidate: TopNCandidateItem | None = None
    excluded_candidates: list[TopNCandidateItem] = Field(default_factory=list)
    selection_log: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
