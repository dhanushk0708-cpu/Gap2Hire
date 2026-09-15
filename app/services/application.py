from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.schemas.application import ApplicationCreate, ApplicationStatus, ApplicationUpdate


class CandidateNotFoundError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class DuplicateApplicationError(Exception):
    pass


async def create_application(
    session: AsyncSession,
    organization_id: UUID,
    data: ApplicationCreate,
) -> Application:
    candidate = await session.get(Candidate, data.candidate_id)
    if candidate is None:
        raise CandidateNotFoundError("Candidate not found")

    job_stmt = select(Job).where(
        Job.id == data.job_id,
        Job.organization_id == organization_id,
    )
    job = await session.scalar(job_stmt)
    if job is None:
        raise JobNotFoundError("Job not found")

    dup_stmt = select(Application).where(
        Application.candidate_id == data.candidate_id,
        Application.job_id == data.job_id,
    )
    existing_app = await session.scalar(dup_stmt)
    if existing_app is not None:
        raise DuplicateApplicationError("Candidate has already applied to this job")

    status_value = (
        data.status.value
        if isinstance(data.status, ApplicationStatus)
        else str(data.status)
    )

    application = Application(
        candidate_id=data.candidate_id,
        job_id=data.job_id,
        status=status_value,
        resume_path=data.resume_path,
    )

    session.add(application)
    try:
        await session.commit()
        await session.refresh(application)
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateApplicationError("Candidate has already applied to this job") from exc

    return application


async def list_applications(
    session: AsyncSession,
    organization_id: UUID,
) -> Sequence[Application]:
    stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(Job.organization_id == organization_id)
        .order_by(Application.applied_at.desc())
    )
    result = await session.scalars(stmt)
    return result.all()


async def get_application_by_id(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> Application | None:
    stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    return await session.scalar(stmt)


async def update_application(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    data: ApplicationUpdate,
) -> Application | None:
    application = await get_application_by_id(session, application_id, organization_id)
    if application is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and isinstance(value, ApplicationStatus):
            value = value.value
        setattr(application, field, value)

    await session.commit()
    await session.refresh(application)
    return application
