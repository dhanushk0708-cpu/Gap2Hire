from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewScheduleCreateRequest(BaseModel):
    application_id: Optional[UUID] = Field(default=None, description="Candidate application ID")
    interviewer_id: Optional[UUID] = Field(default=None, description="User ID of the assigned interviewer")
    scheduled_start: datetime = Field(..., description="Scheduled start time in ISO 8601 format with timezone")
    timezone: str = Field(default="UTC", description="Timezone name, e.g. UTC, America/New_York, Asia/Kolkata")
    duration_minutes: int = Field(default=45, ge=15, le=180, description="Interview duration in minutes (15-180)")
    interview_type: str = Field(default="ONLINE", description="ONLINE or IN_PERSON")
    location: Optional[str] = Field(default=None, description="Physical location or meeting platform details")
    invitation_notes: Optional[str] = Field(default=None, description="Optional custom notes or instructions for candidate")
    plan_id: Optional[UUID] = Field(default=None, description="Approved Interview Plan ID")
    round_id: Optional[UUID] = Field(default=None, description="Specific Interview Plan Round ID")


class InterviewScheduleUpdateRequest(BaseModel):
    scheduled_start: Optional[datetime] = Field(default=None, description="New scheduled start time")
    duration_minutes: Optional[int] = Field(default=None, ge=15, le=180, description="Updated duration in minutes")
    timezone: Optional[str] = Field(default=None, description="Updated timezone")
    interviewer_id: Optional[UUID] = Field(default=None, description="Reassigned interviewer user ID")
    interview_type: Optional[str] = Field(default=None, description="ONLINE or IN_PERSON")
    location: Optional[str] = Field(default=None, description="Updated location or room")
    invitation_notes: Optional[str] = Field(default=None, description="Updated instructions")
    reschedule_reason: Optional[str] = Field(default=None, description="Reason for rescheduling")
    plan_id: Optional[UUID] = Field(default=None, description="Updated Interview Plan ID")
    round_id: Optional[UUID] = Field(default=None, description="Updated Interview Round ID")


class InterviewCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory cancellation reason")


class InterviewScheduleResponse(BaseModel):
    id: UUID
    session_id: UUID
    organization_id: UUID
    application_id: UUID
    interviewer_id: Optional[UUID] = None
    interviewer_name: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    timezone: str
    duration_minutes: int
    calendar_event_id: Optional[str] = None
    meeting_url: Optional[str] = None
    status: str
    interview_type: str
    interview_reference: Optional[str] = None
    location: Optional[str] = None
    cancellation_reason: Optional[str] = None
    booking_token: Optional[str] = None
    plan_id: Optional[UUID] = None
    round_id: Optional[UUID] = None
    candidate_email_sent: bool = False
    candidate_email_id: Optional[str] = None
    invitation_notes: Optional[str] = None
    candidate_id: Optional[UUID] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    job_id: Optional[UUID] = None
    job_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SimulatedNotificationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    interview_schedule_id: Optional[UUID] = None
    recipient: str
    recipient_name: Optional[str] = None
    subject: str
    body: str
    interview_reference: str
    notification_type: str
    delivery_mode: str
    delivery_status: str
    demo_banner: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SlotItemInput(BaseModel):
    start_time: datetime
    duration_minutes: int = Field(default=45, ge=15, le=180)


class PublishBookingSlotsRequest(BaseModel):
    slots: list[SlotItemInput] = Field(..., min_length=1, description="List of proposed availability slots")
    interviewer_id: UUID = Field(..., description="Interviewer hosting the slots")
    interview_type: str = Field(default="ONLINE", description="ONLINE or IN_PERSON")
    location: Optional[str] = Field(default=None)


class BookingSlotResponse(BaseModel):
    id: UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    interview_type: str
    location: Optional[str] = None
    is_booked: bool
    interviewer_name: Optional[str] = None

    model_config = {"from_attributes": True}


class CandidateBookingViewResponse(BaseModel):
    booking_token: str
    job_title: str
    organization_name: str
    candidate_name: str
    interview_type: str
    duration_minutes: int
    slots: list[BookingSlotResponse]
    current_booking: Optional[InterviewScheduleResponse] = None


class BookSlotRequest(BaseModel):
    slot_id: UUID


class CandidateRescheduleRequest(BaseModel):
    slot_id: UUID
    reason: Optional[str] = None


class CandidateCancelRequest(BaseModel):
    reason: Optional[str] = None
