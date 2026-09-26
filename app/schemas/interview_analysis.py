from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PreInterviewCapabilityStatus(BaseModel):
    capability_id: str
    capability_name: str
    importance: str
    provenance: str  # CLAIM, DEMONSTRATED, CORROBORATED, VERIFIED, UNKNOWN, INSUFFICIENT, VERIFICATION_NEEDED
    evidence_strength: str  # STRONG, MODERATE, WEAK, INSUFFICIENT
    status: str  # KNOWN, UNCERTAIN, UNKNOWN
    rationale: str
    source_type: str | None = None
    source_url: str | None = None


class CandidateInterviewPreAnalysis(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    job_id: UUID
    job_title: str
    candidate_strengths: list[dict[str, Any]] = Field(default_factory=list)
    candidate_claims: list[dict[str, Any]] = Field(default_factory=list)
    candidate_unknowns: list[dict[str, Any]] = Field(default_factory=list)
    verification_targets: list[dict[str, Any]] = Field(default_factory=list)
    relevant_concepts: list[str] = Field(default_factory=list)
    recommended_focus: list[dict[str, Any]] = Field(default_factory=list)
    existing_evidence_references: list[dict[str, Any]] = Field(default_factory=list)
    grounded_summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class PreInterviewAnalysis(BaseModel):
    application_id: UUID
    job_id: UUID
    known_capabilities: list[PreInterviewCapabilityStatus] = []
    uncertain_capabilities: list[PreInterviewCapabilityStatus] = []
    unknown_capabilities: list[PreInterviewCapabilityStatus] = []
    claims_to_verify: list[dict[str, Any]] = []
    recommended_focus: list[dict[str, Any]] = []
    candidate_strengths: list[dict[str, Any]] = Field(default_factory=list)
    candidate_claims: list[dict[str, Any]] = Field(default_factory=list)
    candidate_unknowns: list[dict[str, Any]] = Field(default_factory=list)
    verification_targets: list[dict[str, Any]] = Field(default_factory=list)
    relevant_concepts: list[str] = Field(default_factory=list)
    existing_evidence_references: list[dict[str, Any]] = Field(default_factory=list)
    grounded_summary: str = ""
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


class PostInterviewCapabilityFinding(BaseModel):
    capability_id: str
    capability_name: str
    pre_interview_provenance: str = "UNKNOWN"
    post_interview_provenance: str = "UNKNOWN"
    evidence_strength: str = "INSUFFICIENT"
    observation: str = ""
    is_verified_in_interview: bool = False
    source_references: list[dict[str, Any]] = Field(default_factory=list)


class PostInterviewQuestionFinding(BaseModel):
    question_id: str
    sequence_number: int
    question_text: str
    concept: str | None = None
    answer_id: str | None = None
    candidate_answer: str | None = None
    answer_quality: str | None = None
    evidence_state: str | None = None
    reasoning: str | None = None
    follow_up_question: str | None = None
    what_was_demonstrated: str | None = None
    what_remains_uncertain: str | None = None
    source_references: list[dict[str, Any]] = Field(default_factory=list)


class PostInterviewIntegrityObservation(BaseModel):
    event_type: str
    count: int
    occurred_at_list: list[str] = Field(default_factory=list)
    summary: str


class PostInterviewIntegritySummary(BaseModel):
    total_events: int = 0
    observations: list[PostInterviewIntegrityObservation] = Field(default_factory=list)
    raw_event_count_by_type: dict[str, int] = Field(default_factory=dict)
    summary_text: str = "No session integrity anomalies observed."


class PostInterviewHumanRecommendation(BaseModel):
    category: str  # STRENGTH, VERIFICATION_SUGGESTION, UNRESOLVED_AREA, FOLLOW_UP
    topic: str
    detail: str
    provenance_reference: str | None = None


class InterviewReport(BaseModel):
    """Unified Phase 10 Post-Interview Analysis & Evidence Report."""
    id: UUID | None = None
    session_id: UUID
    application_id: UUID
    candidate_name: str | None = None
    candidate_email: str | None = None
    job_id: UUID | None = None
    job_title: str | None = None
    status: str = "COMPLETED"
    generated_at: datetime | None = None
    generation_source: str = "SYSTEM_AI"
    summary: str | None = None
    executive_summary: str | None = None
    strengths: list[dict[str, Any]] = Field(default_factory=list)
    demonstrated_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    claimed_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    unknown_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    verification_needed: list[dict[str, Any]] = Field(default_factory=list)
    evidence_findings: list[dict[str, Any]] = Field(default_factory=list)
    round_summaries: list[dict[str, Any]] = Field(default_factory=list)
    question_findings: list[dict[str, Any]] = Field(default_factory=list)
    follow_up_findings: list[dict[str, Any]] = Field(default_factory=list)
    integrity_summary: dict[str, Any] = Field(default_factory=dict)
    unresolved_areas: list[dict[str, Any]] = Field(default_factory=list)
    recommendations_for_human_review: list[dict[str, Any]] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    total_questions: int = 0
    total_messages: int = 0
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Backwards-compatibility aliases
    pre_interview_analysis: PreInterviewAnalysis | None = None
    evidence_observations: list[dict[str, Any]] = Field(default_factory=list)
    rounds_completed: int = 0
    total_rounds: int = 0
    capabilities_explored: list[str] = Field(default_factory=list)
    questions_asked: int = 0
    remaining_unknowns: list[str] = Field(default_factory=list)
    capabilities_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    transcript_highlights: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
