from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

ALLOWED_CONCURRENCY_LIMITS = {1, 2, 3, 5}


class InterviewBatchStartRequest(BaseModel):
    application_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="List of shortlisted application IDs to create interview sessions for",
    )
    concurrency_limit: int = Field(
        default=2,
        description="Concurrent interview limit. Supported values: 1, 2, 3, 5",
    )
    auto_start: bool = Field(
        default=True,
        description="Whether to immediately transition created sessions to IN_PROGRESS",
    )

    @field_validator("concurrency_limit")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        if v not in ALLOWED_CONCURRENCY_LIMITS:
            raise ValueError(
                f"Invalid concurrency limit '{v}'. Supported values are {sorted(ALLOWED_CONCURRENCY_LIMITS)}."
            )
        return v


class InterviewBatchSessionItem(BaseModel):
    session_id: UUID
    application_id: UUID
    candidate_id: UUID | None = None
    candidate_name: str | None = None
    candidate_email: str | None = None
    job_id: UUID | None = None
    job_title: str | None = None
    status: str
    thread_id: str
    created_at: datetime
    started_at: datetime | None = None


class InterviewBatchStartResponse(BaseModel):
    concurrency_limit: int
    total_requested: int
    sessions_created: int
    sessions: list[InterviewBatchSessionItem]
