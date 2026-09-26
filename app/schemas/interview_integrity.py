from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntegrityEventType(str, Enum):
    TAB_HIDDEN = "TAB_HIDDEN"
    TAB_VISIBLE = "TAB_VISIBLE"
    FULLSCREEN_ENTER = "FULLSCREEN_ENTER"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    CAMERA_CONNECTED = "CAMERA_CONNECTED"
    CAMERA_DISCONNECTED = "CAMERA_DISCONNECTED"
    MICROPHONE_CONNECTED = "MICROPHONE_CONNECTED"
    MICROPHONE_DISCONNECTED = "MICROPHONE_DISCONNECTED"
    CONNECTION_INTERRUPTED = "CONNECTION_INTERRUPTED"
    CONNECTION_RESTORED = "CONNECTION_RESTORED"


def sanitize_integrity_metadata(metadata: Any) -> dict[str, Any]:
    """Ensure metadata is bounded, safe, and contains no executable or deeply nested structures."""
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary")

    # Limit key/value count and payload size
    if len(metadata) > 20:
        raise ValueError("Metadata exceeds maximum allowed fields (20)")

    clean_meta = {}
    for k, v in metadata.items():
        key_str = str(k)[:50]
        if isinstance(v, (str, int, float, bool)) or v is None:
            if isinstance(v, str):
                clean_meta[key_str] = v[:500]
            else:
                clean_meta[key_str] = v
        elif isinstance(v, list):
            clean_meta[key_str] = [str(x)[:100] for x in v[:10]]
        elif isinstance(v, dict):
            clean_meta[key_str] = {str(sub_k)[:30]: str(sub_v)[:100] for sub_k, sub_v in list(v.items())[:5]}
        else:
            clean_meta[key_str] = str(v)[:100]

    return clean_meta


class InterviewIntegrityEventCreate(BaseModel):
    event_type: IntegrityEventType
    occurred_at: datetime | None = Field(default=None, description="Client-side timestamp of observable event")
    metadata: dict[str, Any] | None = Field(default_factory=dict, description="Safe, bounded context data")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: Any) -> dict[str, Any]:
        return sanitize_integrity_metadata(v)

    model_config = ConfigDict(extra="ignore")


class InterviewIntegrityEventResponse(BaseModel):
    id: UUID
    interview_session_id: UUID
    event_type: IntegrityEventType
    occurred_at: datetime
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewIntegrityTimelineResponse(BaseModel):
    session_id: UUID
    total_events: int
    events: list[InterviewIntegrityEventResponse]

    model_config = ConfigDict(extra="ignore")


class WSIntegrityEvent(BaseModel):
    type: Literal["integrity_event"] = "integrity_event"
    event_type: IntegrityEventType
    occurred_at: datetime | None = None
    metadata: dict[str, Any] | None = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_ws_metadata(cls, v: Any) -> dict[str, Any]:
        return sanitize_integrity_metadata(v)

    model_config = ConfigDict(extra="ignore")


class WSIntegrityEventAck(BaseModel):
    type: Literal["integrity_event_recorded"] = "integrity_event_recorded"
    event_type: IntegrityEventType
    event_id: str
    occurred_at: str

    model_config = ConfigDict(extra="ignore")
