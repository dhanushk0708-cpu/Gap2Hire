import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewSession
from app.models.interview_booking_slot import InterviewBookingSlot
from app.models.interview_schedule import InterviewSchedule
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.schemas.interview_schedule import (
    BookingSlotResponse,
    CandidateBookingViewResponse,
    InterviewScheduleResponse,
    SlotItemInput,
)
from app.services.interview import create_interview_session
from app.services.interview_scheduling import (
    InterviewerConflictError,
    InvalidInterviewStateError,
    InvalidScheduleTimeError,
    SchedulingError,
    _to_schedule_response,
    check_interviewer_conflict,
)
from app.services.meeting_links import (
    default_meeting_provider,
    generate_interview_reference,
)
from app.services.simulated_notifications import (
    build_idempotency_key,
    format_booking_confirmation_notification,
    format_cancelled_notification,
    format_rescheduled_notification,
    record_simulated_notification,
)

logger = logging.getLogger(__name__)


class SlotAlreadyBookedError(SchedulingError):
    """Raised when an attempt is made to book an already occupied slot."""
    pass


class InvalidBookingTokenError(SchedulingError):
    """Raised when a candidate booking token is invalid or expired."""
    pass


async def publish_candidate_booking_slots(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    interviewer_id: UUID,
    slots: list[SlotItemInput],
    interview_type: str = "ONLINE",
    location: Optional[str] = None,
) -> tuple[str, list[BookingSlotResponse]]:
    """
    Publishes availability slots for a specific candidate application:
    1. Validates application ownership and interviewer.
    2. Generates an unguessable booking token.
    3. Persists slots in interview_booking_slots.
    4. Returns the booking token and published slot responses.
    """
    app_stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(app_stmt)
    if application is None:
        raise SchedulingError("Application not found or inaccessible")

    interviewer_stmt = select(User).where(
        User.id == interviewer_id,
        User.organization_id == organization_id,
    )
    interviewer = await session.scalar(interviewer_stmt)
    if interviewer is None:
        raise SchedulingError("Interviewer not found in organization")

    # Generate or reuse booking token for this candidate application
    existing_slot_stmt = (
        select(InterviewBookingSlot.booking_token)
        .where(
            InterviewBookingSlot.application_id == application_id,
            InterviewBookingSlot.is_booked == False,
        )
        .limit(1)
    )
    existing_token = await session.scalar(existing_slot_stmt)
    booking_token = existing_token or f"bk_{secrets.token_urlsafe(32)}"

    now_utc = datetime.now(timezone.utc)
    created_slots: list[InterviewBookingSlot] = []

    for item in slots:
        start_utc = item.start_time if item.start_time.tzinfo else item.start_time.replace(tzinfo=timezone.utc)
        if start_utc < now_utc:
            raise InvalidScheduleTimeError("Cannot publish slot in the past.")

        end_time = item.start_time + timedelta(minutes=item.duration_minutes)

        # Check that interviewer does not have existing confirmed schedules during this proposed slot
        await check_interviewer_conflict(
            session=session,
            organization_id=organization_id,
            interviewer_id=interviewer_id,
            start_time=item.start_time,
            end_time=end_time,
        )

        slot = InterviewBookingSlot(
            id=uuid4(),
            organization_id=organization_id,
            application_id=application_id,
            interviewer_id=interviewer_id,
            start_time=item.start_time,
            end_time=end_time,
            duration_minutes=item.duration_minutes,
            interview_type=interview_type.upper(),
            location=location,
            booking_token=booking_token,
            is_booked=False,
        )
        session.add(slot)
        created_slots.append(slot)

    await session.commit()

    return booking_token, [
        BookingSlotResponse(
            id=s.id,
            start_time=s.start_time,
            end_time=s.end_time,
            duration_minutes=s.duration_minutes,
            interview_type=s.interview_type,
            location=s.location,
            is_booked=s.is_booked,
            interviewer_name=interviewer.full_name,
        )
        for s in created_slots
    ]


async def get_candidate_booking_view(
    session: AsyncSession,
    booking_token: str,
) -> CandidateBookingViewResponse:
    """
    Public candidate self-booking view:
    - Resolves application via booking_token.
    - Masks personal details to prevent leaking information.
    - Returns available slots and any existing active booking.
    """
    slots_stmt = (
        select(InterviewBookingSlot)
        .where(InterviewBookingSlot.booking_token == booking_token)
        .options(
            selectinload(InterviewBookingSlot.application).selectinload(Application.job),
            selectinload(InterviewBookingSlot.application).selectinload(Application.candidate),
            selectinload(InterviewBookingSlot.organization),
            selectinload(InterviewBookingSlot.interviewer),
        )
        .order_by(InterviewBookingSlot.start_time.asc())
    )
    all_slots = (await session.scalars(slots_stmt)).all()

    if not all_slots:
        # Also check if an active InterviewSchedule has this booking_token
        sched_stmt = (
            select(InterviewSchedule)
            .where(InterviewSchedule.booking_token == booking_token)
            .options(
                selectinload(InterviewSchedule.application).selectinload(Application.candidate),
                selectinload(InterviewSchedule.application).selectinload(Application.job),
                selectinload(InterviewSchedule.organization),
                selectinload(InterviewSchedule.interviewer),
            )
        )
        sched = await session.scalar(sched_stmt)
        if sched is None:
            raise InvalidBookingTokenError("Invalid or expired booking link.")

        application = sched.application
        org = sched.organization
        current_booking_resp = _to_schedule_response(sched)
        slots_list: list[BookingSlotResponse] = []
    else:
        first_slot = all_slots[0]
        application = first_slot.application
        org = first_slot.organization

        # Check for current active booking
        curr_sched_stmt = (
            select(InterviewSchedule)
            .where(
                InterviewSchedule.application_id == application.id,
                InterviewSchedule.status.in_(["SCHEDULED", "CONFIRMED"]),
            )
            .options(
                selectinload(InterviewSchedule.application).selectinload(Application.candidate),
                selectinload(InterviewSchedule.application).selectinload(Application.job),
                selectinload(InterviewSchedule.interviewer),
            )
            .order_by(InterviewSchedule.created_at.desc())
        )
        curr_sched = await session.scalar(curr_sched_stmt)
        current_booking_resp = _to_schedule_response(curr_sched) if curr_sched else None

        # Return available (unbooked) slots or slots booked by this candidate
        slots_list = [
            BookingSlotResponse(
                id=s.id,
                start_time=s.start_time,
                end_time=s.end_time,
                duration_minutes=s.duration_minutes,
                interview_type=s.interview_type,
                location=s.location,
                is_booked=s.is_booked,
                interviewer_name=s.interviewer.full_name if s.interviewer else None,
            )
            for s in all_slots
        ]

    cand = application.candidate if application else None
    cand_first_name = cand.full_name.split()[0] if cand and cand.full_name else "Candidate"
    job_title = application.job.title if application and application.job else "Position"
    org_name = org.name if org else "Gap2Hire"

    return CandidateBookingViewResponse(
        booking_token=booking_token,
        job_title=job_title,
        organization_name=org_name,
        candidate_name=cand_first_name,
        interview_type=all_slots[0].interview_type if all_slots else "ONLINE",
        duration_minutes=all_slots[0].duration_minutes if all_slots else 45,
        slots=slots_list,
        current_booking=current_booking_resp,
    )


async def book_slot_by_candidate(
    session: AsyncSession,
    booking_token: str,
    slot_id: UUID,
) -> InterviewScheduleResponse:
    """
    Transactional candidate self-booking:
    - Row-level lock (with_for_update) on the target slot to prevent race conditions.
    - Prevents double-booking if two concurrent requests attempt to reserve the same slot.
    - Generates unique reference and demo meeting link.
    - Dispatches simulated confirmation notification.
    """
    # 1. Row-level lock on the target slot
    slot_stmt = (
        select(InterviewBookingSlot)
        .where(
            InterviewBookingSlot.id == slot_id,
            InterviewBookingSlot.booking_token == booking_token,
        )
        .with_for_update()
    )
    slot = await session.scalar(slot_stmt)
    if slot is None:
        raise SchedulingError("Selected booking slot not found or invalid token.")

    if slot.is_booked:
        raise SlotAlreadyBookedError(
            "This time slot has just been reserved. Please select another available slot."
        )

    # 2. Check for interviewer conflicts
    await check_interviewer_conflict(
        session=session,
        organization_id=slot.organization_id,
        interviewer_id=slot.interviewer_id,
        start_time=slot.start_time,
        end_time=slot.end_time,
    )

    # 3. Check if candidate already has an active interview for this application
    existing_sched_stmt = select(InterviewSchedule).where(
        InterviewSchedule.application_id == slot.application_id,
        InterviewSchedule.status.in_(["SCHEDULED", "CONFIRMED"]),
    )
    existing_sched = await session.scalar(existing_sched_stmt)
    if existing_sched is not None:
        raise DuplicateScheduleError(
            f"You already have a confirmed interview for this position on {existing_sched.scheduled_start.strftime('%B %d, %Y at %I:%M %p')}. Please use reschedule if you need to change times."
        )

    # 4. Resolve underlying InterviewSession
    sess_stmt = (
        select(InterviewSession)
        .where(InterviewSession.application_id == slot.application_id)
        .order_by(InterviewSession.created_at.desc())
    )
    interview_session = await session.scalar(sess_stmt)
    if interview_session is None:
        interview_session = await create_interview_session(
            session=session,
            application_id=slot.application_id,
            organization_id=slot.organization_id,
        )

    # 5. Create InterviewSchedule record
    interview_ref = generate_interview_reference()
    meeting_url, cal_event_id = default_meeting_provider.generate_meeting_link(
        interview_reference=interview_ref,
        interview_type=slot.interview_type,
    )

    sched_id = uuid4()
    new_schedule = InterviewSchedule(
        id=sched_id,
        session_id=interview_session.id,
        organization_id=slot.organization_id,
        application_id=slot.application_id,
        interviewer_id=slot.interviewer_id,
        scheduled_start=slot.start_time,
        scheduled_end=slot.end_time,
        timezone="UTC",
        duration_minutes=slot.duration_minutes,
        interview_type=slot.interview_type,
        interview_reference=interview_ref,
        location=slot.location,
        calendar_event_id=cal_event_id,
        meeting_url=meeting_url,
        status="CONFIRMED",
        candidate_email_sent=True,
        candidate_email_id=f"sim_booking_{sched_id.hex[:12]}",
        booking_token=booking_token,
    )
    session.add(new_schedule)

    # 6. Mark slot as booked
    slot.is_booked = True
    slot.booked_schedule_id = new_schedule.id
    await session.flush()

    # 7. Format & Dispatch Simulated Booking Confirmation Email
    app_stmt = (
        select(Application)
        .where(Application.id == slot.application_id)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
    )
    application = await session.scalar(app_stmt)
    cand = application.candidate if application else None
    job = application.job if application else None

    org_stmt = select(Organization).where(Organization.id == slot.organization_id)
    org = await session.scalar(org_stmt)
    org_name = org.name if org else "Gap2Hire"

    cand_name = cand.full_name if cand else "Candidate"
    cand_email = cand.email if cand else "candidate@example.com"
    job_title = job.title if job else "Role"

    subj, body = format_booking_confirmation_notification(
        candidate_name=cand_name,
        job_title=job_title,
        organization_name=org_name,
        scheduled_start=slot.start_time,
        duration_minutes=slot.duration_minutes,
        timezone_name="UTC",
        interview_reference=interview_ref,
        meeting_url=meeting_url,
        location=slot.location,
        interview_type=slot.interview_type,
    )
    idemp_key = build_idempotency_key(interview_ref, "BOOKING_CONFIRMATION", cand_email)
    await record_simulated_notification(
        session=session,
        organization_id=slot.organization_id,
        recipient=cand_email,
        recipient_name=cand_name,
        subject=subj,
        body=body,
        interview_reference=interview_ref,
        notification_type="BOOKING_CONFIRMATION",
        interview_schedule_id=new_schedule.id,
        idempotency_key=idemp_key,
    )

    await session.commit()

    # Re-fetch with all eager relationships
    full_stmt = (
        select(InterviewSchedule)
        .where(InterviewSchedule.id == new_schedule.id)
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
            selectinload(InterviewSchedule.interviewer),
        )
    )
    final_sched = await session.scalar(full_stmt)
    return _to_schedule_response(final_sched)


async def reschedule_slot_by_candidate(
    session: AsyncSession,
    booking_token: str,
    new_slot_id: UUID,
    reason: Optional[str] = None,
) -> InterviewScheduleResponse:
    """
    Candidate self-reschedules their confirmed interview:
    - Validates existing schedule via booking_token.
    - Transactionally locks new slot (`with_for_update`).
    - Releases previous slot (`is_booked = False`).
    - Updates interview schedule timestamps and status.
    - Sends simulated reschedule notification.
    """
    # 1. Find existing active booking
    curr_sched_stmt = (
        select(InterviewSchedule)
        .where(
            InterviewSchedule.booking_token == booking_token,
            InterviewSchedule.status.in_(["SCHEDULED", "CONFIRMED"]),
        )
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
        )
    )
    current_schedule = await session.scalar(curr_sched_stmt)
    if current_schedule is None:
        raise SchedulingError("No active confirmed interview found to reschedule.")

    if current_schedule.status == "COMPLETED":
        raise InvalidInterviewStateError("Cannot reschedule a completed interview.")

    # 2. Lock target new slot
    new_slot_stmt = (
        select(InterviewBookingSlot)
        .where(
            InterviewBookingSlot.id == new_slot_id,
            InterviewBookingSlot.booking_token == booking_token,
        )
        .with_for_update()
    )
    new_slot = await session.scalar(new_slot_stmt)
    if new_slot is None:
        raise SchedulingError("Target slot not found.")
    if new_slot.is_booked:
        raise SlotAlreadyBookedError("The selected time slot is already booked.")

    # 3. Check conflicts for interviewer on new slot
    await check_interviewer_conflict(
        session=session,
        organization_id=current_schedule.organization_id,
        interviewer_id=new_slot.interviewer_id,
        start_time=new_slot.start_time,
        end_time=new_slot.end_time,
        exclude_schedule_id=current_schedule.id,
    )

    # 4. Release old slot
    old_slot_stmt = select(InterviewBookingSlot).where(
        InterviewBookingSlot.booked_schedule_id == current_schedule.id
    )
    old_slot = await session.scalar(old_slot_stmt)
    if old_slot is not None:
        old_slot.is_booked = False
        old_slot.booked_schedule_id = None

    # 5. Update current schedule
    current_schedule.scheduled_start = new_slot.start_time
    current_schedule.scheduled_end = new_slot.end_time
    current_schedule.duration_minutes = new_slot.duration_minutes
    current_schedule.interviewer_id = new_slot.interviewer_id
    current_schedule.interview_type = new_slot.interview_type
    current_schedule.location = new_slot.location
    current_schedule.status = "CONFIRMED"

    # Mark new slot as booked
    new_slot.is_booked = True
    new_slot.booked_schedule_id = current_schedule.id
    await session.flush()

    # 6. Simulated Reschedule Notification
    app_obj = current_schedule.application
    cand = app_obj.candidate if app_obj else None
    job = app_obj.job if app_obj else None
    cand_name = cand.full_name if cand else "Candidate"
    cand_email = cand.email if cand else "candidate@example.com"
    job_title = job.title if job else "Role"

    org_stmt = select(Organization).where(Organization.id == current_schedule.organization_id)
    org = await session.scalar(org_stmt)
    org_name = org.name if org else "Gap2Hire"

    subj, body = format_rescheduled_notification(
        candidate_name=cand_name,
        job_title=job_title,
        organization_name=org_name,
        new_start=new_slot.start_time,
        duration_minutes=new_slot.duration_minutes,
        timezone_name="UTC",
        interview_reference=current_schedule.interview_reference or "REF",
        interview_type=new_slot.interview_type,
        meeting_url=current_schedule.meeting_url,
        location=new_slot.location,
        reason=reason or "Candidate requested time change",
    )
    idemp_key = build_idempotency_key(
        current_schedule.interview_reference or str(current_schedule.id),
        "RESCHEDULE",
        cand_email,
        timestamp_bucket=new_slot.start_time.isoformat(),
    )
    await record_simulated_notification(
        session=session,
        organization_id=current_schedule.organization_id,
        recipient=cand_email,
        recipient_name=cand_name,
        subject=subj,
        body=body,
        interview_reference=current_schedule.interview_reference or "REF",
        notification_type="RESCHEDULE",
        interview_schedule_id=current_schedule.id,
        idempotency_key=idemp_key,
    )

    await session.commit()

    # Re-fetch
    full_stmt = (
        select(InterviewSchedule)
        .where(InterviewSchedule.id == current_schedule.id)
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
            selectinload(InterviewSchedule.interviewer),
        )
    )
    sched = await session.scalar(full_stmt)
    return _to_schedule_response(sched)


async def cancel_booking_by_candidate(
    session: AsyncSession,
    booking_token: str,
    reason: Optional[str] = None,
) -> InterviewScheduleResponse:
    """
    Candidate cancels their booking:
    - Frees the booked slot for future availability.
    - Sets interview schedule status to CANCELLED.
    - Sends simulated cancellation notification.
    """
    curr_sched_stmt = (
        select(InterviewSchedule)
        .where(
            InterviewSchedule.booking_token == booking_token,
            InterviewSchedule.status.in_(["SCHEDULED", "CONFIRMED"]),
        )
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
        )
    )
    sched = await session.scalar(curr_sched_stmt)
    if sched is None:
        raise SchedulingError("No active confirmed interview found to cancel.")

    if sched.status == "COMPLETED":
        raise InvalidInterviewStateError("Cannot cancel a completed interview.")

    # Free associated slot
    slot_stmt = select(InterviewBookingSlot).where(
        InterviewBookingSlot.booked_schedule_id == sched.id
    )
    slot = await session.scalar(slot_stmt)
    if slot is not None:
        slot.is_booked = False
        slot.booked_schedule_id = None

    cancellation_reason = reason or "Candidate cancelled via self-booking page"
    sched.status = "CANCELLED"
    sched.cancellation_reason = cancellation_reason

    # Simulated notification
    app_obj = sched.application
    cand = app_obj.candidate if app_obj else None
    job = app_obj.job if app_obj else None
    cand_name = cand.full_name if cand else "Candidate"
    cand_email = cand.email if cand else "candidate@example.com"
    job_title = job.title if job else "Role"

    org_stmt = select(Organization).where(Organization.id == sched.organization_id)
    org = await session.scalar(org_stmt)
    org_name = org.name if org else "Gap2Hire"

    subj, body = format_cancelled_notification(
        candidate_name=cand_name,
        job_title=job_title,
        organization_name=org_name,
        interview_reference=sched.interview_reference or "REF",
        cancellation_reason=cancellation_reason,
    )
    idemp_key = build_idempotency_key(
        sched.interview_reference or str(sched.id),
        "CANCELLATION",
        cand_email,
    )
    await record_simulated_notification(
        session=session,
        organization_id=sched.organization_id,
        recipient=cand_email,
        recipient_name=cand_name,
        subject=subj,
        body=body,
        interview_reference=sched.interview_reference or "REF",
        notification_type="CANCELLATION",
        interview_schedule_id=sched.id,
        idempotency_key=idemp_key,
    )

    await session.commit()

    full_stmt = (
        select(InterviewSchedule)
        .where(InterviewSchedule.id == sched.id)
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
            selectinload(InterviewSchedule.interviewer),
        )
    )
    updated = await session.scalar(full_stmt)
    return _to_schedule_response(updated)
