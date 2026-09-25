from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_SOURCE_STATUSES = {"DISCOVERED", "QUEUED", "INSPECTED", "SKIPPED", "FAILED"}


class CandidateSourceCreate(BaseModel):
    url: str = Field(min_length=1)
    source_type: str = Field(min_length=1, max_length=50)
    discovered_from: str | None = Field(default=None, max_length=500)
    discovery_depth: int = Field(default=0, ge=0)
    status: str = Field(default="DISCOVERED")
    relevance: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("URL must not be empty")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        status_upper = v.strip().upper()
        if status_upper not in ALLOWED_SOURCE_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(ALLOWED_SOURCE_STATUSES))}")
        return status_upper


class CandidateSourceUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=1)
    source_type: str | None = Field(default=None, min_length=1, max_length=50)
    discovered_from: str | None = Field(default=None, max_length=500)
    discovery_depth: int | None = Field(default=None, ge=0)
    status: str | None = None
    relevance: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] | None = None
    last_inspected_at: datetime | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("URL must not be empty")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is None:
            return None
        status_upper = v.strip().upper()
        if status_upper not in ALLOWED_SOURCE_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(ALLOWED_SOURCE_STATUSES))}")
        return status_upper


class CandidateSourceResponse(BaseModel):
    id: UUID
    application_id: UUID
    url: str
    source_type: str
    discovered_from: str | None = None
    discovery_depth: int = 0
    status: str
    relevance: str | None = None
    title: str | None = None
    metadata: dict[str, Any] | None = None
    last_inspected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def map_metadata(cls, data: Any) -> Any:
        if hasattr(data, "metadata_"):
            return {
                "id": data.id,
                "application_id": data.application_id,
                "url": data.url,
                "source_type": data.source_type,
                "discovered_from": data.discovered_from,
                "discovery_depth": data.discovery_depth,
                "status": data.status,
                "relevance": data.relevance,
                "title": data.title,
                "metadata": data.metadata_,
                "last_inspected_at": data.last_inspected_at,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data
