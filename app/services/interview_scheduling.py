import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewSession
from app.models.interview_plan import InterviewPlan
from app.models.interview_schedule import InterviewSchedule
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.schemas.interview_schedule import InterviewScheduleResponse
from app.services.interview import create_interview_session, get_tenant_interview_session
from app.services.meeting_links import (
    default_meeting_provider,
    generate_interview_reference,
)
from app.services.simulated_notifications import (
    build_idempotency_key,
    format_cancelled_notification,
    format_invitation_notification,
    format_rescheduled_notification,
    record_simulated_notification,
)

logger = logging.getLogger(__name__)


class SchedulingError(Exception):
    """Base exception for interview scheduling errors."""
    pass


class UnapprovedPlanError(SchedulingError):
    """Raised when trying to schedule an interview without an approved plan."""
    pass


class DuplicateScheduleError(SchedulingError):
    """Raised when an interview session or time slot is already scheduled."""
    pass


class InvalidScheduleTimeError(SchedulingError):
    """Raised when scheduled start time or duration is invalid."""
    pass


class InterviewerConflictError(SchedulingError):
    """Raised when the assigned interviewer has an overlapping active interview."""
    pass


class InvalidInterviewStateError(SchedulingError):
    """Raised when an operation is invalid for current interview status."""
    pass


async def check_interviewer_conflict(
    session: AsyncSession,
    organization_id: UUID,
    interviewer_id: UUID,
    start_time: datetime,
    end_time: datetime,
    exclude_schedule_id: Optional[UUID] = None,
) -> None:
    """
    Detects scheduling conflicts for the specified interviewer.
    Checks for overlapping active interviews (SCHEDULED or CONFIRMED).
    """
    stmt = (
        select(InterviewSchedule)
        .where(
            InterviewSchedule.organization_id == organization_id,
            InterviewSchedule.interviewer_id == interviewer_id,
            InterviewSchedule.status.in_(["SCHEDULED", "CONFIRMED"]),
            InterviewSchedule.scheduled_start < end_time,
            InterviewSchedule.scheduled_end > start_time,
        )
    )
    if exclude_schedule_id:
        stmt = stmt.where(InterviewSchedule.id != exclude_schedule_id)

    conflicting = await session.scalar(stmt)
    if conflicting is not None:
        c_start = conflicting.scheduled_start.strftime("%Y-%m-%d %H:%M UTC")
        c_end = conflicting.scheduled_end.strftime("%H:%M UTC")
        ref = conflicting.interview_reference or str(conflicting.id)[:8]
        raise InterviewerConflictError(
            f"Interviewer conflict: Interviewer already has an active interview ({ref}) scheduled from {c_start} to {c_end}."
        )


def _to_schedule_response(sched: InterviewSchedule) -> InterviewScheduleResponse:
    app_obj = sched.application
    cand = app_obj.candidate if app_obj else None
    job = app_obj.job if app_obj else None
    interviewer_user = sched.interviewer

    return InterviewScheduleResponse(
        id=sched.id,
        session_id=sched.session_id,
        organization_id=sched.organization_id,
        application_id=sched.application_id,
        interviewer_id=sched.interviewer_id,
        interviewer_name=interviewer_user.full_name if interviewer_user else None,
        scheduled_start=sched.scheduled_start,
        scheduled_end=sched.scheduled_end,
        timezone=sched.timezone,
        duration_minutes=sched.duration_minutes,
        calendar_event_id=sched.calendar_event_id,
        meeting_url=sched.meeting_url,
        status=sched.status,
        interview_type=sched.interview_type,
        interview_reference=sched.interview_reference,
        location=sched.location,
        cancellation_reason=sched.cancellation_reason,
        booking_token=sched.booking_token,
        plan_id=sched.plan_id,
        round_id=sched.round_id,
        candidate_email_sent=sched.candidate_email_sent,
        candidate_email_id=sched.candidate_email_id,
        invitation_notes=sched.invitation_notes,
        candidate_id=cand.id if cand else None,
        candidate_name=cand.full_name if cand else "Candidate",
        candidate_email=cand.email if cand else "candidate@example.com",
        job_id=job.id if job else None,
        job_title=job.title if job else "Role",
        created_at=sched.created_at,
        updated_at=sched.updated_at,
    )


async def schedule_interview_for_application(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    scheduled_start: datetime,
    timezone_name: str = "UTC",
    duration_minutes: int = 45,
    interviewer_id: Optional[UUID] = None,
    interview_type: str = "ONLINE",
    location: Optional[str] = None,
    invitation_notes: Optional[str] = None,
    created_by: Optional[UUID] = None,
    plan_id: Optional[UUID] = None,
    round_id: Optional[UUID] = None,
) -> InterviewScheduleResponse:
    """
    Schedules an interview for a candidate application:
    1. Validates application ownership and candidate status.
    2. Validates start time (must be future) and duration bounds (15-180 min).
    3. Detects interviewer scheduling conflicts.
    4. Automatically binds/creates underlying InterviewSession.
    5. Generates unique reference (e.g. INT-2026-XXXX) and demo meeting link.
    6. Persists InterviewSchedule record.
    7. Generates and persists simulated demo email notification.
    """
    # 1. Fetch application with validation
    app_stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
    )
    application = await session.scalar(app_stmt)
    if application is None:
        raise SchedulingError("Candidate application not found or inaccessible")

    # 2. Validate time and duration
    now_utc = datetime.now(timezone.utc)
    start_utc = scheduled_start if scheduled_start.tzinfo else scheduled_start.replace(tzinfo=timezone.utc)
    if start_utc < now_utc - timedelta(minutes=5):
        raise InvalidScheduleTimeError("Scheduled start time cannot be in the past.")

    if duration_minutes < 15 or duration_minutes > 180:
        raise InvalidScheduleTimeError("Duration must be between 15 and 180 minutes.")

    scheduled_end = scheduled_start + timedelta(minutes=duration_minutes)

    # 3. Detect Interviewer conflicts
    if interviewer_id:
        # Verify interviewer exists and belongs to the same organization
        interviewer_stmt = select(User).where(
            User.id == interviewer_id,
            User.organization_id == organization_id,
        )
        interviewer = await session.scalar(interviewer_stmt)
        if interviewer is None:
            raise SchedulingError("Assigned interviewer not found in organization.")

        await check_interviewer_conflict(
            session=session,
            organization_id=organization_id,
            interviewer_id=interviewer_id,
            start_time=scheduled_start,
            end_time=scheduled_end,
        )
    else:
        interviewer = None

    # 4. Resolve or initialize InterviewSession
    sess_stmt = (
        select(InterviewSession)
        .where(InterviewSession.application_id == application_id)
        .order_by(InterviewSession.created_at.desc())
    )
    existing_session = await session.scalar(sess_stmt)

    if existing_session is None:
        existing_session = await create_interview_session(
            session=session,
            application_id=application_id,
            organization_id=organization_id,
        )

    # 5. Check if session already has an active schedule
    active_sched_stmt = select(InterviewSchedule).where(
        InterviewSchedule.session_id == existing_session.id,
        InterviewSchedule.status.in_(["SCHEDULED", "CONFIRMED"]),
    )
    existing_sched = await session.scalar(active_sched_stmt)
    if existing_sched is not None:
        raise DuplicateScheduleError(
            f"An active interview is already scheduled for this session on {existing_sched.scheduled_start.isoformat()} ({existing_sched.status})."
        )

    # 6. Auto-resolve approved plan_id if not explicitly provided
    if plan_id is None:
        from app.models.interview_plan import InterviewPlan
        appr_plan_stmt = (
            select(InterviewPlan)
            .where(
                InterviewPlan.application_id == application_id,
                InterviewPlan.organization_id == organization_id,
                InterviewPlan.status == "APPROVED",
            )
            .order_by(InterviewPlan.version.desc())
        )
        appr_plan = await session.scalar(appr_plan_stmt)
        if appr_plan is not None:
            plan_id = appr_plan.id

    # 7. Generate Reference & Demo Meeting Link
    interview_ref = generate_interview_reference()
    meeting_url, cal_event_id = default_meeting_provider.generate_meeting_link(
        interview_reference=interview_ref,
        interview_type=interview_type,
    )
    booking_token = f"bk_{secrets.token_urlsafe(24)}"

    # 8. Persist Schedule
    sched_id = uuid4()
    sched = InterviewSchedule(
        id=sched_id,
        session_id=existing_session.id,
        organization_id=organization_id,
        application_id=application_id,
        interviewer_id=interviewer_id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        timezone=timezone_name,
        duration_minutes=duration_minutes,
        interview_type=interview_type.upper(),
        interview_reference=interview_ref,
        location=location,
        calendar_event_id=cal_event_id,
        meeting_url=meeting_url,
        status="SCHEDULED",
        candidate_email_sent=True,
        candidate_email_id=f"sim_email_{sched_id.hex[:12]}",
        invitation_notes=invitation_notes,
        booking_token=booking_token,
        plan_id=plan_id,
        round_id=round_id,
        created_by=created_by,
    )
    session.add(sched)
    await session.flush()

    # 8. Dispatch Simulated Email Notification
    cand_name = application.candidate.full_name if application.candidate else "Candidate"
    cand_email = application.candidate.email if application.candidate else "candidate@example.com"
    job_title = application.job.title if application.job else "Position"

    org_stmt = select(Organization).where(Organization.id == organization_id)
    org = await session.scalar(org_stmt)
    org_name = org.name if org else "Gap2Hire"

    subj, body = format_invitation_notification(
        candidate_name=cand_name,
        job_title=job_title,
        organization_name=org_name,
        scheduled_start=scheduled_start,
        duration_minutes=duration_minutes,
        timezone_name=timezone_name,
        interview_reference=interview_ref,
        interview_type=interview_type.upper(),
        meeting_url=meeting_url,
        location=location,
        interviewer_name=interviewer.full_name if interviewer else None,
        notes=invitation_notes,
    )
    idemp_key = build_idempotency_key(interview_ref, "INVITATION", cand_email)
    await record_simulated_notification(
        session=session,
        organization_id=organization_id,
        recipient=cand_email,
        recipient_name=cand_name,
        subject=subj,
        body=body,
        interview_reference=interview_ref,
        notification_type="INVITATION",
        interview_schedule_id=sched.id,
        idempotency_key=idemp_key,
    )

    await session.commit()
    await session.refresh(sched)

    # Re-fetch with loaded relations
    return await get_schedule_by_id(session, sched.id, organization_id)


async def get_schedule_by_id(
    session: AsyncSession,
    schedule_id: UUID,
    organization_id: UUID,
) -> InterviewScheduleResponse:
    """Retrieves an interview schedule by ID with tenant isolation."""
    stmt = (
        select(InterviewSchedule)
        .where(
            InterviewSchedule.id == schedule_id,
            InterviewSchedule.organization_id == organization_id,
        )
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
            selectinload(InterviewSchedule.interviewer),
        )
    )
    sched = await session.scalar(stmt)
    if sched is None:
        raise SchedulingError("Interview schedule not found or inaccessible")
    return _to_schedule_response(sched)


async def reschedule_interview(
    session: AsyncSession,
    schedule_id: UUID,
    organization_id: UUID,
    new_start: Optional[datetime] = None,
    new_duration: Optional[int] = None,
    new_timezone: Optional[str] = None,
    new_interviewer_id: Optional[UUID] = None,
    new_interview_type: Optional[str] = None,
    new_location: Optional[str] = None,
    new_notes: Optional[str] = None,
    reschedule_reason: Optional[str] = None,
) -> InterviewScheduleResponse:
    """
    Reschedules an active interview schedule:
    - Validates schedule state (cannot reschedule COMPLETED or CANCELLED).
    - Checks interviewer conflicts for new time or reassigned interviewer.
    - Updates demo meeting link if type changed.
    - Persists changes and simulated notification.
    """
    stmt = (
        select(InterviewSchedule)
        .where(
            InterviewSchedule.id == schedule_id,
            InterviewSchedule.organization_id == organization_id,
        )
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
            selectinload(InterviewSchedule.interviewer),
        )
    )
    sched = await session.scalar(stmt)
    if sched is None:
        raise SchedulingError("Interview schedule not found")

    if sched.status in ["COMPLETED", "CANCELLED"]:
        raise InvalidInterviewStateError(
            f"Cannot reschedule an interview in status '{sched.status}'."
        )

    target_start = new_start or sched.scheduled_start
    target_duration = new_duration or sched.duration_minutes
    target_interviewer_id = new_interviewer_id if new_interviewer_id is not None else sched.interviewer_id
    target_type = new_interview_type.upper() if new_interview_type else sched.interview_type

    now_utc = datetime.now(timezone.utc)
    start_utc = target_start if target_start.tzinfo else target_start.replace(tzinfo=timezone.utc)
    if start_utc < now_utc - timedelta(minutes=5):
        raise InvalidScheduleTimeError("Rescheduled start time cannot be in the past.")

    if target_duration < 15 or target_duration > 180:
        raise InvalidScheduleTimeError("Duration must be between 15 and 180 minutes.")

    target_end = target_start + timedelta(minutes=target_duration)

    # Check conflicts
    if target_interviewer_id:
        await check_interviewer_conflict(
            session=session,
            organization_id=organization_id,
            interviewer_id=target_interviewer_id,
            start_time=target_start,
            end_time=target_end,
            exclude_schedule_id=sched.id,
        )

    # Update meeting url if type changed
    if target_type != sched.interview_type:
        sched.meeting_url, sched.calendar_event_id = default_meeting_provider.generate_meeting_link(
            interview_reference=sched.interview_reference or str(sched.id)[:8],
            interview_type=target_type,
        )

    sched.scheduled_start = target_start
    sched.scheduled_end = target_end
    sched.duration_minutes = target_duration
    if new_timezone:
        sched.timezone = new_timezone
    if new_interviewer_id is not None:
        sched.interviewer_id = new_interviewer_id
    sched.interview_type = target_type
    if new_location is not None:
        sched.location = new_location
    if new_notes is not None:
        sched.invitation_notes = new_notes

    # Keep status as CONFIRMED or SCHEDULED
    if sched.status != "CONFIRMED":
        sched.status = "SCHEDULED"

    # Send simulated notification
    app_obj = sched.application
    cand = app_obj.candidate if app_obj else None
    job = app_obj.job if app_obj else None
    cand_name = cand.full_name if cand else "Candidate"
    cand_email = cand.email if cand else "candidate@example.com"
    job_title = job.title if job else "Role"

    org_stmt = select(Organization).where(Organization.id == organization_id)
    org = await session.scalar(org_stmt)
    org_name = org.name if org else "Gap2Hire"

    subj, body = format_rescheduled_notification(
        candidate_name=cand_name,
        job_title=job_title,
        organization_name=org_name,
        new_start=target_start,
        duration_minutes=target_duration,
        timezone_name=sched.timezone,
        interview_reference=sched.interview_reference or "REF",
        interview_type=target_type,
        meeting_url=sched.meeting_url,
        location=sched.location,
        reason=reschedule_reason,
    )
    idemp_key = build_idempotency_key(
        sched.interview_reference or str(sched.id),
        "RESCHEDULE",
        cand_email,
        timestamp_bucket=target_start.isoformat(),
    )
    await record_simulated_notification(
        session=session,
        organization_id=organization_id,
        recipient=cand_email,
        recipient_name=cand_name,
        subject=subj,
        body=body,
        interview_reference=sched.interview_reference or "REF",
        notification_type="RESCHEDULE",
        interview_schedule_id=sched.id,
        idempotency_key=idemp_key,
    )

    await session.commit()
    return await get_schedule_by_id(session, sched.id, organization_id)


async def cancel_interview(
    session: AsyncSession,
    schedule_id: UUID,
    organization_id: UUID,
    cancellation_reason: str,
) -> InterviewScheduleResponse:
    """
    Cancels an active interview schedule:
    - Sets status to CANCELLED.
    - Records cancellation reason.
    - Dispatches simulated cancellation notification.
    """
    stmt = (
        select(InterviewSchedule)
        .where(
            InterviewSchedule.id == schedule_id,
            InterviewSchedule.organization_id == organization_id,
        )
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
        )
    )
    sched = await session.scalar(stmt)
    if sched is None:
        raise SchedulingError("Interview schedule not found")

    if sched.status == "CANCELLED":
        raise InvalidInterviewStateError("Interview is already cancelled.")
    if sched.status == "COMPLETED":
        raise InvalidInterviewStateError("Cannot cancel a completed interview.")

    sched.status = "CANCELLED"
    sched.cancellation_reason = cancellation_reason

    # Send simulated notification
    app_obj = sched.application
    cand = app_obj.candidate if app_obj else None
    job = app_obj.job if app_obj else None
    cand_name = cand.full_name if cand else "Candidate"
    cand_email = cand.email if cand else "candidate@example.com"
    job_title = job.title if job else "Role"

    org_stmt = select(Organization).where(Organization.id == organization_id)
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
        organization_id=organization_id,
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
    return await get_schedule_by_id(session, sched.id, organization_id)


async def mark_interview_completed(
    session: AsyncSession,
    schedule_id: UUID,
    organization_id: UUID,
) -> InterviewScheduleResponse:
    """
    Marks an interview as COMPLETED.
    Synchronously transitions the underlying InterviewSession status to 'COMPLETED'
    to enable post-interview scorecard generation and candidate workflow advancement.
    """
    stmt = (
        select(InterviewSchedule)
        .where(
            InterviewSchedule.id == schedule_id,
            InterviewSchedule.organization_id == organization_id,
        )
        .options(selectinload(InterviewSchedule.session))
    )
    sched = await session.scalar(stmt)
    if sched is None:
        raise SchedulingError("Interview schedule not found")

    if sched.status == "CANCELLED":
        raise InvalidInterviewStateError("Cannot mark a cancelled interview as completed.")

    sched.status = "COMPLETED"

    # Transition underlying InterviewSession
    if sched.session:
        sched.session.status = "COMPLETED"
        if not sched.session.ended_at:
            sched.session.ended_at = datetime.now(timezone.utc)

    await session.commit()
    return await get_schedule_by_id(session, sched.id, organization_id)


async def list_interviews(
    session: AsyncSession,
    organization_id: UUID,
    status_filter: Optional[str] = None,
    candidate_query: Optional[str] = None,
    interviewer_id: Optional[UUID] = None,
    application_id: Optional[UUID] = None,
    target_date: Optional[date] = None,
) -> list[InterviewScheduleResponse]:
    """
    Retrieves and filters interview schedules with strict organization scoping.
    """
    stmt = (
        select(InterviewSchedule)
        .join(Application, Application.id == InterviewSchedule.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(InterviewSchedule.organization_id == organization_id)
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
            selectinload(InterviewSchedule.interviewer),
        )
        .order_by(InterviewSchedule.scheduled_start.asc())
    )

    if status_filter:
        stmt = stmt.where(InterviewSchedule.status == status_filter.upper())

    if interviewer_id:
        stmt = stmt.where(InterviewSchedule.interviewer_id == interviewer_id)

    if application_id:
        stmt = stmt.where(InterviewSchedule.application_id == application_id)

    if candidate_query:
        cq = f"%{candidate_query.strip()}%"
        stmt = stmt.where(
            or_(
                Candidate.full_name.ilike(cq),
                Candidate.email.ilike(cq),
                InterviewSchedule.interview_reference.ilike(cq),
            )
        )

    if target_date:
        # Match day boundaries in UTC
        start_of_day = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_of_day = start_of_day + timedelta(days=1)
        stmt = stmt.where(
            InterviewSchedule.scheduled_start >= start_of_day,
            InterviewSchedule.scheduled_start < end_of_day,
        )

    results = (await session.scalars(stmt)).all()
    return [_to_schedule_response(s) for s in results]


# Retain backward compatibility helper for existing callers
def format_candidate_invitation_email(
    candidate_name: str,
    job_title: str,
    organization_name: str,
    scheduled_start: datetime,
    duration_minutes: int,
    timezone_name: str,
    meeting_url: str,
    invitation_notes: Optional[str] = None,
) -> dict[str, str]:
    subj, body = format_invitation_notification(
        candidate_name=candidate_name,
        job_title=job_title,
        organization_name=organization_name,
        scheduled_start=scheduled_start,
        duration_minutes=duration_minutes,
        timezone_name=timezone_name,
        interview_reference="INT-DEMO",
        meeting_url=meeting_url,
        notes=invitation_notes,
    )
    return {
        "subject": subj,
        "body": body,
        "meeting_url": meeting_url,
    }


async def schedule_interview_for_session(
    session: AsyncSession,
    session_id: UUID,
    scheduled_start: datetime,
    timezone_name: str,
    duration_minutes: int,
    organization_id: UUID,
    invitation_notes: Optional[str] = None,
    created_by: Optional[UUID] = None,
) -> InterviewScheduleResponse:
    """Legacy helper scheduling by session_id."""
    interview_session = await get_tenant_interview_session(session, session_id, organization_id)
    if interview_session is None:
        raise SchedulingError("Interview session not found")

    # Check for approved plan
    plan_stmt = (
        select(InterviewPlan)
        .where(
            InterviewPlan.application_id == interview_session.application_id,
            InterviewPlan.organization_id == organization_id,
            InterviewPlan.status == "APPROVED",
        )
        .order_by(InterviewPlan.version.desc())
    )
    approved_plan = await session.scalar(plan_stmt)
    if approved_plan is None:
        raise UnapprovedPlanError("Cannot schedule interview: No approved interview plan found for this candidate.")

    # Check for duplicate
    existing_sched_stmt = select(InterviewSchedule).where(
        InterviewSchedule.session_id == interview_session.id,
        InterviewSchedule.organization_id == organization_id,
        InterviewSchedule.status == "SCHEDULED",
    )
    existing_sched = await session.scalar(existing_sched_stmt)
    if existing_sched is not None:
        raise DuplicateScheduleError(
            f"Interview is already scheduled for {existing_sched.scheduled_start.isoformat()} ({existing_sched.timezone})."
        )

    # Validate time
    now_utc = datetime.now(timezone.utc)
    start_utc = scheduled_start if scheduled_start.tzinfo else scheduled_start.replace(tzinfo=timezone.utc)
    if start_utc < now_utc - timedelta(minutes=5):
        raise InvalidScheduleTimeError("Scheduled start time cannot be in the past.")

    if duration_minutes < 15 or duration_minutes > 180:
        raise InvalidScheduleTimeError("Duration must be between 15 and 180 minutes.")

    return await schedule_interview_for_application(
        session=session,
        application_id=interview_session.application_id,
        organization_id=organization_id,
        scheduled_start=scheduled_start,
        timezone_name=timezone_name,
        duration_minutes=duration_minutes,
        invitation_notes=invitation_notes,
        created_by=created_by,
    )


async def get_interview_schedule(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
) -> Optional[InterviewScheduleResponse]:
    """Retrieves schedule details by session ID."""
    stmt = (
        select(InterviewSchedule)
        .where(
            InterviewSchedule.session_id == session_id,
            InterviewSchedule.organization_id == organization_id,
        )
        .options(
            selectinload(InterviewSchedule.application).selectinload(Application.candidate),
            selectinload(InterviewSchedule.application).selectinload(Application.job),
            selectinload(InterviewSchedule.interviewer),
        )
        .order_by(InterviewSchedule.created_at.desc())
    )
    sched = await session.scalar(stmt)
    if sched is None:
        return None
    return _to_schedule_response(sched)
