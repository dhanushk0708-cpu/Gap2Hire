from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CapabilityImportance(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CapabilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    importance: CapabilityImportance = CapabilityImportance.MEDIUM


class CapabilityBatchCreate(BaseModel):
    capabilities: list[CapabilityCreate] = Field(min_length=1)


class CapabilityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    importance: CapabilityImportance | None = None


class CapabilityResponse(BaseModel):
    id: UUID
    job_id: UUID
    name: str
    description: str | None
    importance: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
