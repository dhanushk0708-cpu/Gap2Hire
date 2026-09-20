from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VerificationType(str, Enum):
    PRACTICAL_TASK = "PRACTICAL_TASK"
    ASSESSMENT = "ASSESSMENT"
    INTERVIEW = "INTERVIEW"


class VerificationStatus(str, Enum):
    REQUESTED = "REQUESTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    CANCELLED = "CANCELLED"


class VerificationResult(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


class VerificationCreate(BaseModel):
    capability_id: UUID
    type: VerificationType
    instructions: str | None = Field(default=None)


class VerificationSubmit(BaseModel):
    submission_content: str = Field(min_length=1)


class VerificationReview(BaseModel):
    result: VerificationResult
    review_notes: str | None = Field(default=None)


class VerificationResponse(BaseModel):
    id: UUID
    application_id: UUID
    capability_id: UUID
    type: str
    status: str
    instructions: str | None
    submission_content: str | None = None
    result: str | None
    review_notes: str | None
    requested_by: UUID | None
    reviewed_by: UUID | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
