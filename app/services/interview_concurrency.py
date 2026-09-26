import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.interview import InterviewMessage, InterviewSession
from app.models.job import Job
from app.schemas.interview_batch import (
    ALLOWED_CONCURRENCY_LIMITS,
    InterviewBatchSessionItem,
    InterviewBatchStartResponse,
)
from app.services.application import ApplicationNotFoundError
from app.services.interview import (
    CandidateNotShortlistedError,
    NoApprovedCapabilitiesError,
)

logger = logging.getLogger(__name__)


class InvalidConcurrencyLimitError(Exception):
    """Raised when an unsupported concurrency limit is requested."""
    pass


class BatchApplicationError(Exception):
    """Raised when batch applications fail tenant or validation checks."""
    pass


class DuplicateActiveSessionError(Exception):
    """Raised when an active session already exists for an application in the batch."""
    pass


def validate_concurrency_limit(concurrency_limit: int) -> int:
    """Validates that concurrency is one of {1, 2, 3, 5}."""
    if concurrency_limit not in ALLOWED_CONCURRENCY_LIMITS:
        raise InvalidConcurrencyLimitError(
            f"Invalid concurrency limit '{concurrency_limit}'. Supported values are {sorted(ALLOWED_CONCURRENCY_LIMITS)}."
        )
    return concurrency_limit


def get_session_thread_id(session_id: UUID) -> str:
    """Returns the dedicated LangGraph thread identifier for an InterviewSession."""
    return str(session_id)


async def create_batch_interview_sessions(
    session: AsyncSession,
    organization_id: UUID,
    application_ids: list[UUID],
    concurrency_limit: int = 2,
    auto_start: bool = True,
) -> InterviewBatchStartResponse:
    """
    Creates and optionally initializes independent InterviewSessions for multiple applications.
    Guarantees tenant isolation, candidate eligibility, duplicate active session prevention,
    and individual LangGraph thread assignment.
    """
    validate_concurrency_limit(concurrency_limit)

    if not application_ids:
        raise BatchApplicationError("At least one application ID must be provided.")

    # Deduplicate requested IDs preserving order
    unique_app_ids = list(dict.fromkeys(application_ids))

    # Fetch all applications belonging to the organization
    app_stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .where(
            Application.id.in_(unique_app_ids),
            Job.organization_id == organization_id,
        )
    )
    db_apps = (await session.scalars(app_stmt)).all()
    apps_by_id = {app.id: app for app in db_apps}

    # Verify all applications were found and belong to this tenant
    for app_id in unique_app_ids:
        if app_id not in apps_by_id:
            raise ApplicationNotFoundError(
                f"Application '{app_id}' not found or belongs to another organization."
            )

    # Check for existing active sessions for these applications
    existing_sessions_stmt = select(InterviewSession).where(
        InterviewSession.application_id.in_(unique_app_ids),
        InterviewSession.status.in_(["CREATED", "IN_PROGRESS"]),
    )
    existing_active = (await session.scalars(existing_sessions_stmt)).all()
    if existing_active:
        active_app_ids = [str(s.application_id) for s in existing_active]
        raise DuplicateActiveSessionError(
            f"Active interview sessions already exist for applications: {', '.join(active_app_ids)}."
        )

    # Validate each candidate eligibility and capabilities
    sessions_to_create: list[InterviewSession] = []
    response_items: list[InterviewBatchSessionItem] = []

    for app_id in unique_app_ids:
        application = apps_by_id[app_id]

        # Verify candidate shortlist status
        if (
            application.status == "NOT_SHORTLISTED"
            or application.shortlist_status in ("NOT_SHORTLISTED", "HOLD")
            or (
                application.shortlist_status == "PENDING"
                and application.status in ("SCREENING", "RECEIVED", "HOLD", "NOT_SHORTLISTED")
            )
        ):
            cand_name = application.candidate.full_name if application.candidate else "Candidate"
            raise CandidateNotShortlistedError(
                f"Cannot create interview session for {cand_name} ({application.id}): Candidate is not shortlisted."
            )

        # Verify job capabilities exist
        caps_stmt = select(Capability).where(Capability.job_id == application.job_id)
        capabilities = (await session.scalars(caps_stmt)).all()
        if not capabilities:
            raise NoApprovedCapabilitiesError(
                f"Job '{application.job_id}' has no approved capabilities for an interview."
            )

        # Create independent InterviewSession
        new_session = InterviewSession(
            id=uuid4(),
            application_id=application.id,
            status="IN_PROGRESS" if auto_start else "CREATED",
            started_at=datetime.utcnow() if auto_start else None,
        )
        session.add(new_session)
        sessions_to_create.append(new_session)

    # Flush so session IDs are generated
    await session.flush()

    for idx, new_session in enumerate(sessions_to_create):
        app_id = unique_app_ids[idx]
        application = apps_by_id[app_id]

        if auto_start:
            sys_msg = InterviewMessage(
                session_id=new_session.id,
                role="SYSTEM",
                content="Interview session started.",
                sequence_number=1,
            )
            session.add(sys_msg)

        cand = application.candidate
        job = application.job
        response_items.append(
            InterviewBatchSessionItem(
                session_id=new_session.id,
                application_id=application.id,
                candidate_id=cand.id if cand else None,
                candidate_name=cand.full_name if cand else None,
                candidate_email=cand.email if cand else None,
                job_id=job.id if job else None,
                job_title=job.title if job else None,
                status=new_session.status,
                thread_id=get_session_thread_id(new_session.id),
                created_at=new_session.created_at or datetime.utcnow(),
                started_at=new_session.started_at,
            )
        )

    await session.commit()
    logger.info(
        f"Successfully created {len(sessions_to_create)} concurrent interview sessions with limit {concurrency_limit} for org {organization_id}."
    )

    return InterviewBatchStartResponse(
        concurrency_limit=concurrency_limit,
        total_requested=len(unique_app_ids),
        sessions_created=len(sessions_to_create),
        sessions=response_items,
    )
