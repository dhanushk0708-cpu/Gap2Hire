import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.roles import UserRole
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewSession
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.job import Job
from app.models.user import User
from app.schemas.interview_integrity import (
    IntegrityEventType,
    sanitize_integrity_metadata,
)

logger = logging.getLogger(__name__)


class IntegrityServiceError(Exception):
    """Base exception for integrity service operations."""
    pass


class IntegritySessionNotFoundError(IntegrityServiceError):
    """Raised when the target interview session does not exist in the tenant."""
    pass


class IntegritySessionAccessDeniedError(IntegrityServiceError):
    """Raised when a candidate attempts to record or view events for another session."""
    pass


class InvalidIntegrityEventTypeError(IntegrityServiceError):
    """Raised when an unrecognized integrity event signal is reported."""
    pass


async def get_authorized_interview_session_for_integrity(
    session: AsyncSession,
    session_id: UUID,
    user: User,
) -> InterviewSession:
    """
    Validates tenant isolation and candidate session ownership.
    Returns the session or raises appropriate integrity service exceptions.
    """
    stmt = (
        select(InterviewSession)
        .join(Application, Application.id == InterviewSession.application_id)
        .join(Job, Job.id == Application.job_id)
        .options(
            selectinload(InterviewSession.application).selectinload(Application.candidate),
            selectinload(InterviewSession.application).selectinload(Application.job),
        )
        .where(
            InterviewSession.id == session_id,
            Job.organization_id == user.organization_id,
        )
    )
    interview_session = await session.scalar(stmt)
    if interview_session is None:
        raise IntegritySessionNotFoundError(f"Interview session {session_id} not found.")

    if user.role == UserRole.CANDIDATE.value:
        if (
            not interview_session.application
            or not interview_session.application.candidate
            or interview_session.application.candidate.email.strip().lower() != user.email.strip().lower()
        ):
            raise IntegritySessionAccessDeniedError(
                "Candidate is not authorized to interact with this interview session."
            )

    return interview_session


async def record_integrity_event(
    session: AsyncSession,
    session_id: UUID,
    event_type: str | IntegrityEventType,
    user: User,
    occurred_at: datetime | None = None,
    metadata: dict | None = None,
) -> InterviewIntegrityEvent:
    """
    Persist an observable integrity event for an authorized interview session.
    """
    # 1. Validate event_type
    if isinstance(event_type, str):
        try:
            validated_type = IntegrityEventType(event_type)
        except ValueError:
            raise InvalidIntegrityEventTypeError(f"Invalid integrity event type '{event_type}'.")
    elif isinstance(event_type, IntegrityEventType):
        validated_type = event_type
    else:
        raise InvalidIntegrityEventTypeError(f"Unsupported event type format: {type(event_type)}")

    # 2. Validate session & authorization
    interview_session = await get_authorized_interview_session_for_integrity(
        session=session,
        session_id=session_id,
        user=user,
    )

    # 3. Sanitize metadata & timestamp
    clean_metadata = sanitize_integrity_metadata(metadata)
    event_time = occurred_at or datetime.now(timezone.utc)

    # 4. Create and persist event
    integrity_event = InterviewIntegrityEvent(
        id=uuid4(),
        interview_session_id=interview_session.id,
        event_type=validated_type.value,
        occurred_at=event_time,
        metadata_json=clean_metadata,
        created_at=datetime.now(timezone.utc),
    )
    session.add(integrity_event)
    await session.commit()
    await session.refresh(integrity_event)

    logger.info(
        f"Recorded integrity signal '{validated_type.value}' for session {session_id} by user {user.id}"
    )
    return integrity_event


async def get_session_integrity_timeline(
    session: AsyncSession,
    session_id: UUID,
    user: User,
) -> list[InterviewIntegrityEvent]:
    """
    Retrieve chronological integrity events for an authorized session.
    """
    interview_session = await get_authorized_interview_session_for_integrity(
        session=session,
        session_id=session_id,
        user=user,
    )

    stmt = (
        select(InterviewIntegrityEvent)
        .where(InterviewIntegrityEvent.interview_session_id == interview_session.id)
        .order_by(InterviewIntegrityEvent.occurred_at.asc())
    )
    events = (await session.scalars(stmt)).all()
    return list(events)
