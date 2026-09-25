from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceProvenance(str, Enum):
    CLAIM = "CLAIM"
    CORROBORATED = "CORROBORATED"
    VERIFIED = "VERIFIED"
    DEMONSTRATED = "DEMONSTRATED"
    PERFORMANCE = "PERFORMANCE"


class CapabilityEvidenceState(str, Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class AIEvidenceItem(BaseModel):
    capability_name: str = Field(min_length=1)
    strength: EvidenceStrength
    evidence: str | None = Field(default=None)


class AIEvidencePayload(BaseModel):
    evidence: list[AIEvidenceItem]


class EvidenceCreate(BaseModel):
    capability_id: UUID
    source_type: str = Field(default="OTHER", max_length=50)
    strength: EvidenceStrength = EvidenceStrength.MODERATE
    provenance: EvidenceProvenance = EvidenceProvenance.CLAIM
    content: Optional[str] = None
    candidate_source_id: Optional[UUID] = None
    source_id: Optional[UUID] = None

    @model_validator(mode="before")
    @classmethod
    def reconcile_source_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            src_id = data.get("source_id")
            cand_src_id = data.get("candidate_source_id")
            if cand_src_id is None and src_id is not None:
                data["candidate_source_id"] = src_id
            elif src_id is None and cand_src_id is not None:
                data["source_id"] = cand_src_id
        return data


class EvidenceResponse(BaseModel):
    id: UUID
    application_id: UUID
    capability_id: UUID
    candidate_source_id: Optional[UUID] = None
    source_id: Optional[UUID] = None
    source_type: str
    content: Optional[str]
    strength: str
    provenance: EvidenceProvenance = EvidenceProvenance.CLAIM
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_source_ids(cls, data: Any) -> Any:
        if hasattr(data, "candidate_source_id"):
            val = getattr(data, "candidate_source_id")
            return {
                "id": data.id,
                "application_id": data.application_id,
                "capability_id": data.capability_id,
                "candidate_source_id": val,
                "source_id": val,
                "source_type": data.source_type,
                "content": data.content,
                "strength": data.strength,
                "provenance": getattr(data, "provenance", "CLAIM") or "CLAIM",
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        elif isinstance(data, dict):
            src_id = data.get("candidate_source_id") or data.get("source_id")
            data["candidate_source_id"] = src_id
            data["source_id"] = src_id
        return data


class CapabilityEvidenceSummary(BaseModel):
    capability_id: UUID
    name: str
    state: CapabilityEvidenceState
    strength: EvidenceStrength
    provenance: EvidenceProvenance = EvidenceProvenance.CLAIM
    evidence: Optional[str] = Field(default=None)
    candidate_source_id: Optional[UUID] = None
    source_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_summary_source_ids(cls, data: Any) -> Any:
        if hasattr(data, "candidate_source_id"):
            val = getattr(data, "candidate_source_id")
            return {
                "capability_id": data.capability_id,
                "name": data.name,
                "state": data.state,
                "strength": data.strength,
                "provenance": getattr(data, "provenance", "CLAIM") or "CLAIM",
                "evidence": data.evidence,
                "candidate_source_id": val,
                "source_id": val,
            }
        elif isinstance(data, dict):
            src_id = data.get("candidate_source_id") or data.get("source_id")
            data["candidate_source_id"] = src_id
            data["source_id"] = src_id
        return data


class ApplicationEvidenceSummary(BaseModel):
    application_id: UUID
    capabilities: list[CapabilityEvidenceSummary]

    model_config = ConfigDict(from_attributes=True)
