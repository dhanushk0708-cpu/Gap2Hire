from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.schemas.job import JobCreate, JobStatus, JobUpdate


async def create_job(
    session: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
    data: JobCreate,
) -> Job:
    status_value = (
        data.status.value
        if isinstance(data.status, JobStatus)
        else str(data.status)
    )

    job = Job(
        organization_id=organization_id,
        created_by=user_id,
        title=data.title,
        description=data.description,
        status=status_value,
    )

    session.add(job)
    await session.commit()
    await session.refresh(job)

    return job


async def list_jobs(
    session: AsyncSession,
    organization_id: UUID,
) -> Sequence[Job]:
    result = await session.scalars(
        select(Job)
        .where(Job.organization_id == organization_id)
        .order_by(Job.created_at.desc())
    )
    return result.all()


async def get_job_by_id(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> Job | None:
    return await session.scalar(
        select(Job).where(
            Job.id == job_id,
            Job.organization_id == organization_id,
        )
    )


async def update_job(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
    data: JobUpdate,
) -> Job | None:
    job = await get_job_by_id(session, job_id, organization_id)
    if job is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and isinstance(value, JobStatus):
            value = value.value
        setattr(job, field, value)

    await session.commit()
    await session.refresh(job)
    return job


async def delete_job(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> bool:
    job = await get_job_by_id(session, job_id, organization_id)
    if job is None:
        return False

    await session.delete(job)
    await session.commit()
    return True
