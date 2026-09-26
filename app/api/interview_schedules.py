from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.application import Application
from app.models.interview import InterviewSession
from app.models.user import User
from app.schemas.interview_schedule import (
    InterviewScheduleCreateRequest,
    InterviewScheduleResponse,
)
from app.services.interview import (
    CandidateNotShortlistedError,
    InterviewSessionNotFoundError,
    create_interview_session,
    get_tenant_interview_session,
)
from app.services.interview_scheduling import (
    DuplicateScheduleError,
    InvalidScheduleTimeError,
    SchedulingError,
    UnapprovedPlanError,
    get_interview_schedule,
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


@router.post(
    "/api/v1/interviews/{session_id}/schedule",
    response_model=InterviewScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_interview_endpoint(
    session_id: UUID,
    body: InterviewScheduleCreateRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Schedules an interview for an approved plan session:
    - Generates calendar event with Google Meet link.
    - Sends candidate email invitation.
    - Persists schedule details.
    """
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
async def get_interview_schedule_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieves schedule details for an interview session."""
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
async def schedule_application_interview_endpoint(
    application_id: UUID,
    body: InterviewScheduleCreateRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Convenience endpoint to schedule an interview directly from the Application/Interview Plan page.
    Automatically resolves or initializes the session if needed.
    """
    # Find existing session for application
    sess_stmt = (
        select(InterviewSession)
        .where(
            InterviewSession.application_id == application_id,
        )
        .order_by(InterviewSession.created_at.desc())
    )
    existing_sess = await session.scalar(sess_stmt)

    if existing_sess is None:
        try:
            created_sess = await create_interview_session(
                session=session,
                application_id=application_id,
                organization_id=current_user.organization_id,
            )
            session_id = created_sess.id
        except CandidateNotShortlistedError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    else:
        session_id = existing_sess.id

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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DuplicateScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidScheduleTimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
