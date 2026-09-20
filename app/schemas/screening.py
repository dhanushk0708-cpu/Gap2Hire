from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequirementEvaluation(BaseModel):
    requirement_name: str
    requirement_type: str = "CAPABILITY"  # "EXPERIENCE", "CAPABILITY", "QUALIFICATION", "CUSTOM"
    status: str = "NEEDS_REVIEW"  # "MET", "NOT_MET", "UNKNOWN", "NEEDS_REVIEW"
    evidence_found: str | None = None
    provenance: str | None = "CLAIM"  # "CLAIM", "VERIFIED", "UNKNOWN"
    strength: str | None = None  # "STRONG", "MODERATE", "WEAK"
    reason: str = ""


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
    requirements_evaluated: list[RequirementEvaluation] = Field(default_factory=list)
    claims_summary: list[str] = Field(default_factory=list)
    unknowns_summary: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    summary_explanation: str = ""
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
    applied_at: datetime
    has_resume: bool
    is_interview_ready: bool

    model_config = ConfigDict(from_attributes=True)
