from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchDecision(BaseModel):
    """
    Structured LLM decision specifying which unresolved capability to investigate,
    which candidate source to inspect, and what evidence target to look for.
    """
    capability_id: UUID = Field(description="UUID of the unresolved capability to investigate")
    source_id: UUID = Field(description="UUID of the CandidateSource to inspect")
    reason: str = Field(description="Reasoning explaining why this source was selected for this capability")
    evidence_target: str = Field(description="Concrete artifact or skill demonstration to search for")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Reasoning confidence in source suitability (NOT a candidate skill score)",
    )


class EvidenceExtractionResult(BaseModel):
    """
    Structured extraction result assessing whether an inspected source contains
    concrete, grounded evidence supporting a candidate's capability.
    """
    capability_id: UUID
    supported: bool = Field(description="True only if source contains factual proof of the capability")
    claim: Optional[str] = Field(default=None, description="Concrete evidence statement supported by the source")
    explanation: str = Field(description="Audit explanation of findings in the source")
    source_excerpt: Optional[str] = Field(default=None, description="Direct relevant quote or excerpt from source")
    strength: str = Field(default="MODERATE", description="Evidence strength: STRONG, MODERATE, WEAK, INSUFFICIENT")
    provenance: str = Field(default="DEMONSTRATED", description="Provenance: DEMONSTRATED, CORROBORATED, VERIFIED")


class ResearchRunResult(BaseModel):
    """
    Summary returned by the research agent service upon completing a session run.
    """
    model_config = ConfigDict(from_attributes=True)

    research_session_id: UUID
    application_id: UUID
    status: str
    iterations_run: int
    sources_inspected: int
    evidence_items_created: int
    stop_reason: Optional[str] = None
    capability_summary: dict[str, str] = {}
