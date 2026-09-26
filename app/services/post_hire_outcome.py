from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.capability import Capability
from app.models.job import Job
from app.models.post_hire_outcome import PostHireOutcome
from app.models.user import User
from app.schemas.post_hire_outcome import (
    OutcomeStatus,
    PostHireOutcomeCreate,
    PostHireOutcomeListResponse,
    PostHireOutcomeResponse,
)


class ApplicationNotFoundError(Exception):
    pass


class PostHireOutcomeNotFoundError(Exception):
    pass


class InvalidOutcomeStatusError(Exception):
    pass


class InvalidCapabilityError(Exception):
    pass


VALID_OUTCOME_STATUSES = {s.value for s in OutcomeStatus}


def _build_outcome_response(
    outcome: PostHireOutcome,
    application: Application,
    job: Job,
    recorder: User,
) -> PostHireOutcomeResponse:
    cand_name = getattr(application.candidate, "full_name", None) or getattr(application.candidate, "name", "Candidate")
    return PostHireOutcomeResponse(
        id=outcome.id,
        application_id=outcome.application_id,
        job_id=job.id,
        job_title=job.title,
        candidate_id=application.candidate_id,
        candidate_name=cand_name,
        recorded_by=outcome.recorded_by,
        recorded_by_name=recorder.full_name or recorder.email if recorder else "Hiring Manager",
        recorded_at=outcome.recorded_at,
        outcome_period=outcome.outcome_period,
        capability_id=outcome.capability_id,
        capability_name=outcome.capability_name,
        expected_capability_description=outcome.expected_capability_description,
        observed_outcome_description=outcome.observed_outcome_description,
        outcome_status=outcome.outcome_status,
        manager_notes=outcome.manager_notes,
        evidence_reference=outcome.evidence_reference,
        metadata=outcome.metadata_json or {},
        created_at=outcome.created_at or outcome.recorded_at,
    )


async def record_post_hire_outcome(
    session: AsyncSession,
    application_id: UUID,
    user: User,
    data: PostHireOutcomeCreate,
) -> PostHireOutcomeResponse:
    """Records an evidence-based post-hire work outcome observation."""
    status_clean = data.outcome_status.value if hasattr(data.outcome_status, "value") else str(data.outcome_status)
    if status_clean not in VALID_OUTCOME_STATUSES:
        raise InvalidOutcomeStatusError(
            f"Invalid outcome status '{data.outcome_status}'. Must be one of: {', '.join(sorted(VALID_OUTCOME_STATUSES))}"
        )

    # 1. Fetch application with tenant verification
    stmt = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == user.organization_id,
        )
    )
    application = await session.scalar(stmt)
    if not application:
        raise ApplicationNotFoundError("Application not found or inaccessible under current tenant.")

    job = application.job

    # 2. Validate capability if capability_id is supplied
    if data.capability_id:
        cap = await session.get(Capability, data.capability_id)
        if not cap or cap.job_id != job.id:
            raise InvalidCapabilityError("Specified capability is not associated with this job.")

    now = datetime.utcnow()
    outcome_record = PostHireOutcome(
        id=uuid4(),
        application_id=application.id,
        job_id=job.id,
        recorded_by=user.id,
        recorded_at=now,
        outcome_period=data.outcome_period,
        capability_id=data.capability_id,
        capability_name=data.capability_name.strip(),
        expected_capability_description=data.expected_capability_description,
        observed_outcome_description=data.observed_outcome_description.strip(),
        outcome_status=status_clean,
        manager_notes=data.manager_notes,
        evidence_reference=data.evidence_reference,
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    session.add(outcome_record)
    await session.commit()
    await session.refresh(outcome_record)

    return _build_outcome_response(
        outcome=outcome_record,
        application=application,
        job=job,
        recorder=user,
    )


async def list_post_hire_outcomes(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> PostHireOutcomeListResponse:
    """Lists all post-hire outcome records for an application."""
    stmt = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(stmt)
    if not application:
        raise ApplicationNotFoundError("Application not found or inaccessible under current tenant.")

    outcomes_stmt = (
        select(PostHireOutcome)
        .options(selectinload(PostHireOutcome.recorder))
        .where(PostHireOutcome.application_id == application_id)
        .order_by(PostHireOutcome.recorded_at.desc())
    )
    res = await session.execute(outcomes_stmt)
    outcomes_list = res.scalars().all()

    items = [
        _build_outcome_response(
            outcome=o,
            application=application,
            job=application.job,
            recorder=o.recorder or await session.get(User, o.recorded_by),
        )
        for o in outcomes_list
    ]

    cand_name = getattr(application.candidate, "full_name", None) or getattr(application.candidate, "name", "Candidate")

    return PostHireOutcomeListResponse(
        application_id=application.id,
        candidate_id=application.candidate_id,
        candidate_name=cand_name,
        outcomes=items,
        total_outcomes=len(items),
    )


async def get_post_hire_outcome(
    session: AsyncSession,
    application_id: UUID,
    outcome_id: UUID,
    organization_id: UUID,
) -> PostHireOutcomeResponse:
    """Retrieves a single post-hire outcome record."""
    stmt = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(stmt)
    if not application:
        raise ApplicationNotFoundError("Application not found or inaccessible under current tenant.")

    outcome_stmt = (
        select(PostHireOutcome)
        .options(selectinload(PostHireOutcome.recorder))
        .where(
            PostHireOutcome.id == outcome_id,
            PostHireOutcome.application_id == application_id,
        )
    )
    outcome = await session.scalar(outcome_stmt)
    if not outcome:
        raise PostHireOutcomeNotFoundError("Post-hire outcome record not found.")

    return _build_outcome_response(
        outcome=outcome,
        application=application,
        job=application.job,
        recorder=outcome.recorder or await session.get(User, outcome.recorded_by),
    )
