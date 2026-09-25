from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_SESSION_STATUSES = {"PENDING", "RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"}
ALLOWED_CAPABILITY_STATES = {"UNKNOWN", "INVESTIGATING", "SUFFICIENT", "INSUFFICIENT", "VERIFICATION_NEEDED"}


class ResearchSessionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResearchCapabilityStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    INVESTIGATING = "INVESTIGATING"
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    VERIFICATION_NEEDED = "VERIFICATION_NEEDED"


class ResearchEventType(str, Enum):
    SESSION_STARTED = "SESSION_STARTED"
    SOURCE_SELECTED = "SOURCE_SELECTED"
    SOURCE_INSPECTION_STARTED = "SOURCE_INSPECTION_STARTED"
    SOURCE_INSPECTION_COMPLETED = "SOURCE_INSPECTION_COMPLETED"
    SOURCE_INSPECTION_FAILED = "SOURCE_INSPECTION_FAILED"
    LINKS_DISCOVERED = "LINKS_DISCOVERED"
    EVIDENCE_FOUND = "EVIDENCE_FOUND"
    CAPABILITY_UPDATED = "CAPABILITY_UPDATED"
    RESEARCH_PAUSED = "RESEARCH_PAUSED"
    RESEARCH_RESUMED = "RESEARCH_RESUMED"
    RESEARCH_COMPLETED = "RESEARCH_COMPLETED"
    RESEARCH_FAILED = "RESEARCH_FAILED"


class ResearchSessionCreate(BaseModel):
    metadata: Optional[dict[str, Any]] = None


class ResearchSessionUpdate(BaseModel):
    status: Optional[str] = None
    current_source_id: Optional[UUID] = None
    stop_reason: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    completed_at: Optional[datetime] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        upper_v = v.strip().upper()
        if upper_v not in ALLOWED_SESSION_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(ALLOWED_SESSION_STATUSES))}")
        return upper_v


class ResearchCapabilityStateUpdate(BaseModel):
    state: str
    reason: Optional[str] = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        upper_v = v.strip().upper()
        if upper_v not in ALLOWED_CAPABILITY_STATES:
            raise ValueError(f"state must be one of: {', '.join(sorted(ALLOWED_CAPABILITY_STATES))}")
        return upper_v


class ResearchEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    source_id: Optional[UUID] = None
    capability_id: Optional[UUID] = None
    message: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ResearchCapabilityStateResponse(BaseModel):
    id: UUID
    research_session_id: UUID
    capability_id: UUID
    state: str
    reason: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResearchEventResponse(BaseModel):
    id: UUID
    research_session_id: UUID
    event_type: str
    source_id: Optional[UUID] = None
    capability_id: Optional[UUID] = None
    message: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def map_metadata(cls, data: Any) -> Any:
        if hasattr(data, "metadata_"):
            return {
                "id": data.id,
                "research_session_id": data.research_session_id,
                "event_type": data.event_type,
                "source_id": data.source_id,
                "capability_id": data.capability_id,
                "message": data.message,
                "metadata": data.metadata_,
                "created_at": data.created_at,
            }
        return data


class ResearchSessionResponse(BaseModel):
    id: UUID
    application_id: UUID
    status: str
    current_source_id: Optional[UUID] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    last_activity_at: datetime
    stop_reason: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def map_metadata(cls, data: Any) -> Any:
        if hasattr(data, "metadata_"):
            res = {
                "id": data.id,
                "application_id": data.application_id,
                "status": data.status,
                "current_source_id": data.current_source_id,
                "started_at": data.started_at,
                "completed_at": data.completed_at,
                "last_activity_at": data.last_activity_at,
                "stop_reason": data.stop_reason,
                "metadata": data.metadata_,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
            loaded_dict = getattr(data, "__dict__", {})
            if "capability_states" in loaded_dict and loaded_dict["capability_states"] is not None:
                res["capability_states"] = loaded_dict["capability_states"]
            if "events" in loaded_dict and loaded_dict["events"] is not None:
                res["events"] = loaded_dict["events"]
            return res
        return data


class ResearchSessionDetailResponse(ResearchSessionResponse):
    capability_states: list[ResearchCapabilityStateResponse] = []
    events: list[ResearchEventResponse] = []
