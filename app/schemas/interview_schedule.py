from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewScheduleCreateRequest(BaseModel):
    scheduled_start: datetime = Field(..., description="Scheduled start time in ISO 8601 format with timezone")
    timezone: str = Field(default="UTC", description="Timezone name, e.g. UTC, America/New_York, Asia/Kolkata")
    duration_minutes: int = Field(default=45, ge=15, le=180, description="Interview duration in minutes (15-180)")
    invitation_notes: str | None = Field(default=None, description="Optional custom notes or instructions for candidate")


class InterviewScheduleResponse(BaseModel):
    id: UUID
    session_id: UUID
    organization_id: UUID
    application_id: UUID
    scheduled_start: datetime
    scheduled_end: datetime
    timezone: str
    duration_minutes: int
    calendar_event_id: str | None = None
    meeting_url: str
    status: str
    candidate_email_sent: bool = False
    candidate_email_id: str | None = None
    invitation_notes: str | None = None
    candidate_name: str | None = None
    candidate_email: str | None = None
    job_title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
