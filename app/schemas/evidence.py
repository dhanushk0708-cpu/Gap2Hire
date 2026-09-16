from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"


class CapabilityEvidenceState(str, Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class AIEvidenceItem(BaseModel):
    capability_name: str = Field(min_length=1)
    strength: EvidenceStrength
    evidence: str | None = Field(default=None)


class AIEvidencePayload(BaseModel):
    evidence: list[AIEvidenceItem]


class EvidenceResponse(BaseModel):
    id: UUID
    application_id: UUID
    capability_id: UUID
    source_type: str
    content: str | None
    strength: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CapabilityEvidenceSummary(BaseModel):
    capability_id: UUID
    name: str
    state: CapabilityEvidenceState
    strength: EvidenceStrength
    evidence: str | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True)


class ApplicationEvidenceSummary(BaseModel):
    application_id: UUID
    capabilities: list[CapabilityEvidenceSummary]

    model_config = ConfigDict(from_attributes=True)
