from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.simulated_notification import SimulatedNotification
from app.models.user import User
from app.schemas.interview_schedule import (
    BookSlotRequest,
    BookingSlotResponse,
    CandidateBookingViewResponse,
    CandidateCancelRequest,
    CandidateRescheduleRequest,
    InterviewCancelRequest,
    InterviewScheduleCreateRequest,
    InterviewScheduleResponse,
    InterviewScheduleUpdateRequest,
    PublishBookingSlotsRequest,
    SimulatedNotificationResponse,
)
from app.services.interview_booking import (
    InvalidBookingTokenError,
    SlotAlreadyBookedError,
    book_slot_by_candidate,
    cancel_booking_by_candidate,
    get_candidate_booking_view,
    publish_candidate_booking_slots,
    reschedule_slot_by_candidate,
)
from app.services.interview_scheduling import (
    DuplicateScheduleError,
    InterviewerConflictError,
    InvalidInterviewStateError,
    InvalidScheduleTimeError,
    SchedulingError,
    UnapprovedPlanError,
    cancel_interview,
    get_interview_schedule,
    get_schedule_by_id,
    list_interviews,
    mark_interview_completed,
    reschedule_interview,
    schedule_interview_for_application,
    schedule_interview_for_session,
)

router = APIRouter(
    tags=["Interview Scheduling"],
)

require_interview_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


# ==========================================
# HR INTERVIEW MANAGEMENT ENDPOINTS
# ==========================================

@router.get(
    "/api/v1/interviews/interviewers",
    response_model=list[dict],
    status_code=status.HTTP_200_OK,
)
async def list_interviewers_endpoint(
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Returns active team members within the tenant organization who can conduct interviews."""
    stmt = (
        select(User)
        .where(
            User.organization_id == current_user.organization_id,
            User.is_active == True,
        )
        .order_by(User.full_name.asc())
    )
    users = (await session.scalars(stmt)).all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
        }
        for u in users
    ]


@router.get(
    "/api/v1/interviews/schedules",
    response_model=list[InterviewScheduleResponse],
    status_code=status.HTTP_200_OK,
)
async def list_interviews_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    candidate_query: Optional[str] = Query(None, alias="candidate"),
    interviewer_id: Optional[UUID] = Query(None, alias="interviewer_id"),
    application_id: Optional[UUID] = Query(None, alias="application_id"),
    target_date: Optional[date] = Query(None, alias="date"),
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Lists and filters interviews scoped strictly to the current organization."""
    return await list_interviews(
        session=session,
        organization_id=current_user.organization_id,
        status_filter=status_filter,
        candidate_query=candidate_query,
        interviewer_id=interviewer_id,
        application_id=application_id,
        target_date=target_date,
    )


@router.post(
    "/api/v1/interviews/schedules",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_interview_endpoint(
    body: InterviewScheduleCreateRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Schedules an interview for a candidate application:
    - Detects interviewer scheduling conflicts
    - Generates unique reference and demo meeting link
    - Dispatches simulated email notification
    """
    if not body.application_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="application_id is required to schedule an interview.",
        )
    try:
        return await schedule_interview_for_application(
            session=session,
            application_id=body.application_id,
            organization_id=current_user.organization_id,
            scheduled_start=body.scheduled_start,
            timezone_name=body.timezone,
            duration_minutes=body.duration_minutes,
            interviewer_id=body.interviewer_id,
            interview_type=body.interview_type,
            location=body.location,
            invitation_notes=body.invitation_notes,
            created_by=current_user.id,
            plan_id=body.plan_id,
            round_id=body.round_id,
        )
    except InterviewerConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DuplicateScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidScheduleTimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/api/v1/interviews/schedules/{schedule_id}",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_200_OK,
)
async def get_schedule_endpoint(
    schedule_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieves schedule details by ID."""
    try:
        return await get_schedule_by_id(
            session=session,
            schedule_id=schedule_id,
            organization_id=current_user.organization_id,
        )
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/api/v1/interviews/schedules/{schedule_id}/reschedule",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_200_OK,
)
async def reschedule_interview_endpoint(
    schedule_id: UUID,
    body: InterviewScheduleUpdateRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Reschedules an existing interview, validating new slot against interviewer conflicts."""
    try:
        return await reschedule_interview(
            session=session,
            schedule_id=schedule_id,
            organization_id=current_user.organization_id,
            new_start=body.scheduled_start,
            new_duration=body.duration_minutes,
            new_timezone=body.timezone,
            new_interviewer_id=body.interviewer_id,
            new_interview_type=body.interview_type,
            new_location=body.location,
            new_notes=body.invitation_notes,
            reschedule_reason=body.reschedule_reason,
        )
    except InterviewerConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidScheduleTimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidInterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/api/v1/interviews/schedules/{schedule_id}/cancel",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_interview_endpoint(
    schedule_id: UUID,
    body: InterviewCancelRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Cancels an active interview schedule with a reason."""
    try:
        return await cancel_interview(
            session=session,
            schedule_id=schedule_id,
            organization_id=current_user.organization_id,
            cancellation_reason=body.reason,
        )
    except InvalidInterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/api/v1/interviews/schedules/{schedule_id}/complete",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_200_OK,
)
async def complete_interview_endpoint(
    schedule_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Marks an interview as completed, advancing session state for post-interview scorecards."""
    try:
        return await mark_interview_completed(
            session=session,
            schedule_id=schedule_id,
            organization_id=current_user.organization_id,
        )
    except InvalidInterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ==========================================
# SIMULATED NOTIFICATIONS HISTORY
# ==========================================

@router.get(
    "/api/v1/interviews/notifications",
    response_model=list[SimulatedNotificationResponse],
    status_code=status.HTTP_200_OK,
)
async def list_notifications_endpoint(
    schedule_id: Optional[UUID] = Query(None),
    interview_reference: Optional[str] = Query(None),
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieves simulated notification history for inspection in the UI."""
    stmt = (
        select(SimulatedNotification)
        .where(SimulatedNotification.organization_id == current_user.organization_id)
        .order_by(SimulatedNotification.created_at.desc())
    )
    if schedule_id:
        stmt = stmt.where(SimulatedNotification.interview_schedule_id == schedule_id)
    if interview_reference:
        stmt = stmt.where(SimulatedNotification.interview_reference == interview_reference)

    return (await session.scalars(stmt)).all()


# ==========================================
# CANDIDATE SELF-BOOKING SLOTS PUBLISHING
# ==========================================

@router.post(
    "/api/v1/applications/{application_id}/booking-slots",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def publish_slots_endpoint(
    application_id: UUID,
    body: PublishBookingSlotsRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Allows HR to publish self-booking slots for a specific candidate application."""
    try:
        token, published = await publish_candidate_booking_slots(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
            interviewer_id=body.interviewer_id,
            slots=body.slots,
            interview_type=body.interview_type,
            location=body.location,
        )
        return {
            "booking_token": token,
            "booking_url": f"/book-interview/{token}",
            "total_slots": len(published),
            "slots": [p.model_dump() for p in published],
        }
    except InterviewerConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidScheduleTimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ==========================================
# PUBLIC CANDIDATE SELF-BOOKING ENDPOINTS
# (NO AUTH REQUIRED — SECURED BY BOOKING TOKEN)
# ==========================================

@router.get(
    "/api/v1/booking/{booking_token}/slots",
    response_model=CandidateBookingViewResponse,
    status_code=status.HTTP_200_OK,
)
async def get_booking_slots_endpoint(
    booking_token: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Public endpoint for candidates to view available booking slots."""
    try:
        return await get_candidate_booking_view(session=session, booking_token=booking_token)
    except InvalidBookingTokenError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/api/v1/booking/{booking_token}/book",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def book_slot_endpoint(
    booking_token: str,
    body: BookSlotRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Public endpoint for candidate to reserve a slot with transaction locking."""
    try:
        return await book_slot_by_candidate(
            session=session,
            booking_token=booking_token,
            slot_id=body.slot_id,
        )
    except SlotAlreadyBookedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InterviewerConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DuplicateScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/booking/{booking_token}/reschedule",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_200_OK,
)
async def candidate_reschedule_endpoint(
    booking_token: str,
    body: CandidateRescheduleRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Public endpoint for candidate to reschedule their interview to a new slot."""
    try:
        return await reschedule_slot_by_candidate(
            session=session,
            booking_token=booking_token,
            new_slot_id=body.slot_id,
            reason=body.reason,
        )
    except SlotAlreadyBookedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InterviewerConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidInterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/booking/{booking_token}/cancel",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_200_OK,
)
async def candidate_cancel_endpoint(
    booking_token: str,
    body: CandidateCancelRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Public endpoint for candidate to cancel their scheduled interview."""
    try:
        return await cancel_booking_by_candidate(
            session=session,
            booking_token=booking_token,
            reason=body.reason,
        )
    except InvalidInterviewStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ==========================================
# BACKWARD COMPATIBILITY ENDPOINTS
# ==========================================

@router.post(
    "/api/v1/interviews/{session_id}/schedule",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_interview_by_session_endpoint(
    session_id: UUID,
    body: InterviewScheduleCreateRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Schedules an interview for an approved plan session."""
    try:
        return await schedule_interview_for_session(
            session=session,
            session_id=session_id,
            scheduled_start=body.scheduled_start,
            timezone_name=body.timezone,
            duration_minutes=body.duration_minutes,
            organization_id=current_user.organization_id,
            invitation_notes=body.invitation_notes,
            created_by=current_user.id,
        )
    except UnapprovedPlanError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except DuplicateScheduleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidScheduleTimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SchedulingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/v1/interviews/{session_id}/schedule",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_200_OK,
)
async def get_interview_schedule_by_session_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieves schedule details by session ID."""
    schedule = await get_interview_schedule(
        session=session,
        session_id=session_id,
        organization_id=current_user.organization_id,
    )
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview schedule found for this session.",
        )
    return schedule



@router.post(
    "/api/v1/applications/{application_id}/schedule",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_application_interview_legacy_endpoint(
    application_id: UUID,
    body: InterviewScheduleCreateRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Direct application scheduling endpoint."""
    try:
        return await schedule_interview_for_application(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
            scheduled_start=body.scheduled_start,
            timezone_name=body.timezone,
            duration_minutes=body.duration_minutes,
            interviewer_id=body.interviewer_id,
            interview_type=body.interview_type,
            location=body.location,
            invitation_notes=body.invitation_notes,
            created_by=current_user.id,
            plan_id=body.plan_id,
            round_id=body.round_id,
        )
    except InterviewerConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DuplicateScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidScheduleTimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
