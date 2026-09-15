from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApplicationStatus(str, Enum):
    APPLIED = "APPLIED"
    IN_REVIEW = "IN_REVIEW"
    VERIFICATION = "VERIFICATION"
    INTERVIEW = "INTERVIEW"
    HIRED = "HIRED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class ApplicationCreate(BaseModel):
    candidate_id: UUID
    job_id: UUID
    status: ApplicationStatus = ApplicationStatus.APPLIED
    resume_path: str | None = Field(default=None, max_length=512)


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    resume_path: str | None = Field(default=None, max_length=512)


class ApplicationResponse(BaseModel):
    id: UUID
    candidate_id: UUID
    job_id: UUID
    status: str
    resume_path: str | None
    resume_text: str | None = None
    applied_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
