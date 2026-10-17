from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class AggregatedFinding(BaseModel):
    """Aggregated view of a single autopsy finding across applications."""
    capability_name: Optional[str] = Field(
        None, description="Capability name if the finding is tied to a specific capability"
    )
    category: str = Field(..., description="Finding category as emitted by AutopsyFinding.category")
    summary: str = Field(..., description="Human‑readable description of the finding (first occurrence)")
    count: int = Field(..., description="Number of applications that produced this finding")
    application_ids: List[UUID] = Field(default_factory=list, description="Application IDs that contributed")
    job_ids: List[UUID] = Field(default_factory=list, description="Job IDs associated with the applications")
    outcome_ids: List[UUID] = Field(
        default_factory=list,
        description="Post‑hire outcome IDs referenced by the finding, if any",
    )
    evidence_ids: List[UUID] = Field(
        default_factory=list,
        description="Evidence record IDs referenced by the finding, if any",
    )

    model_config = ConfigDict(from_attributes=True)


class AggregatedRecommendation(BaseModel):
    """Aggregated AI improvement suggestion derived from Autopsy suggestions."""
    capability_name: Optional[str] = Field(
        None, description="Capability the suggestion applies to, if any"
    )
    suggestion_text: str = Field(..., description="The AI‑generated recommendation text")
    count: int = Field(..., description="How many applications produced this exact suggestion")
    application_ids: List[UUID] = Field(default_factory=list, description="Applications supporting the suggestion")
    supporting_records: List[str] = Field(
        default_factory=list,
        description="Human‑readable identifiers (e.g., outcome status, job title) that were used to build the suggestion",
    )
    confidence_strength: Optional[str] = Field(
        None, description="Confidence tag copied from AIImprovementSuggestion.confidence_strength if present"
    )
    action_type: Optional[str] = Field(
        None, description="Action type from AIImprovementSuggestion.action_type if present"
    )

    model_config = ConfigDict(from_attributes=True)


class HiringIntelligenceResponse(BaseModel):
    total_applications: int = Field(..., description="Number of applications examined for the tenant")
    applications_with_outcomes: int = Field(
        ..., description="Applications that have at least one PostHireOutcome record"
    )
    applications_without_outcomes: int = Field(
        ..., description="Applications that have no post‑hire outcome data"
    )
    total_outcome_records: int = Field(
        ..., description="Sum of all PostHireOutcome rows across the considered applications"
    )
    findings: List[AggregatedFinding] = Field(default_factory=list)
    recommendations: List[AggregatedRecommendation] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    message: Optional[str] = Field(
        None,
        description="Human‑readable note when data is insufficient to produce useful insights",
    )

    model_config = ConfigDict(from_attributes=True)
