from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.capability import CapabilityImportance


class SuggestedCapability(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str
    importance: CapabilityImportance

    model_config = ConfigDict(from_attributes=True)


class JDAnalysisResponse(BaseModel):
    job_id: UUID
    suggested_capabilities: list[SuggestedCapability]

    model_config = ConfigDict(from_attributes=True)


class ExtractedCapabilitiesPayload(BaseModel):
    capabilities: list[SuggestedCapability]
