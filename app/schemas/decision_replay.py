from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DecisionContext(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str | None = None
    job_id: UUID
    job_title: str
    decision: str
    decision_reason: str
    decided_by_id: UUID
    decided_by_name: str
    decided_at: datetime
    application_status: str
    report_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class ScreeningSnapshotContext(BaseModel):
    screening_status: str
    screening_notes: str | None = None
    shortlist_status: str
    shortlist_reason: str | None = None
    hard_requirement_coverage: float | None = None
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    verification_needs: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EvidenceSnapshotItem(BaseModel):
    capability_id: UUID | None = None
    capability_name: str
    state: str
    source_type: str | None = None
    source_url: str | None = None
    evidence_excerpt: str | None = None
    confidence: str | None = None
    provenance_summary: str | None = None

    model_config = ConfigDict(from_attributes=True)


class InterviewSnapshotContext(BaseModel):
    report_id: UUID | None = None
    session_id: UUID | None = None
    interview_status: str | None = None
    report_summary: str | None = None
    demonstrated_capabilities: list[str] = Field(default_factory=list)
    claimed_capabilities: list[str] = Field(default_factory=list)
    unknown_capabilities: list[str] = Field(default_factory=list)
    verification_needed: list[str] = Field(default_factory=list)
    unresolved_areas: list[str] = Field(default_factory=list)
    question_count: int = 0
    round_count: int = 0
    integrity_events_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DecisionReplayResponse(BaseModel):
    application_id: UUID
    job_id: UUID
    candidate_id: UUID
    reconstructed_at: datetime
    decision_context: DecisionContext
    screening_context: ScreeningSnapshotContext
    evidence_context: list[EvidenceSnapshotItem] = Field(default_factory=list)
    interview_context: InterviewSnapshotContext | None = None
    unresolved_areas: list[str] = Field(default_factory=list)
    decision_history: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
