from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PreInterviewCapabilityStatus(BaseModel):
    capability_id: str
    capability_name: str
    importance: str
    provenance: str
    evidence_strength: str
    status: str  # KNOWN, UNCERTAIN, UNKNOWN
    rationale: str


class PreInterviewAnalysis(BaseModel):
    application_id: UUID
    job_id: UUID
    known_capabilities: list[PreInterviewCapabilityStatus] = []
    uncertain_capabilities: list[PreInterviewCapabilityStatus] = []
    unknown_capabilities: list[PreInterviewCapabilityStatus] = []
    claims_to_verify: list[dict[str, Any]] = []
    recommended_focus: list[dict[str, Any]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnswerAnalysisObservation(BaseModel):
    capability_id: str | None = None
    capability_name: str | None = None
    question_intent: str | None = None
    observation: str
    provenance: str = "INTERVIEW"
    confidence: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    missing_information: str | None = None
    contradictions_noted: str | None = None
    follow_up_needed: bool = False
    follow_up_focus: str | None = None


class PostInterviewRoundSummary(BaseModel):
    round_id: str
    round_name: str
    round_type: str
    sequence: int
    status: str
    capabilities_tested: list[str] = []
    questions_asked: int = 0
    followups_used: int = 0
    evidence_observed: list[dict[str, Any]] = []
    unknowns_remaining: list[str] = []


class InterviewReport(BaseModel):
    session_id: UUID
    application_id: UUID
    job_id: UUID
    status: str
    pre_interview_analysis: PreInterviewAnalysis | None = None
    rounds_summary: list[PostInterviewRoundSummary] = []
    evidence_observations: list[dict[str, Any]] = []
    total_questions: int = 0
    total_messages: int = 0
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
