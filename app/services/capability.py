from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capability import Capability
from app.models.job import Job
from app.schemas.capability import CapabilityCreate, CapabilityImportance, CapabilityUpdate


async def get_job_for_organization(
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


async def create_capability(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
    data: CapabilityCreate,
) -> Capability | None:
    job = await get_job_for_organization(session, job_id, organization_id)
    if job is None:
        return None

    importance_value = (
        data.importance.value
        if isinstance(data.importance, CapabilityImportance)
        else str(data.importance)
    )

    capability = Capability(
        job_id=job_id,
        name=data.name,
        description=data.description,
        importance=importance_value,
    )

    session.add(capability)
    await session.commit()
    await session.refresh(capability)

    return capability

async def create_capabilities_batch(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
    capabilities_data: list[CapabilityCreate],
) -> list[Capability] | None:
    job = await get_job_for_organization(session, job_id, organization_id)
    if job is None:
        return None

    created_capabilities: list[Capability] = []
    for data in capabilities_data:
        importance_value = (
            data.importance.value
            if isinstance(data.importance, CapabilityImportance)
            else str(data.importance)
        )
        capability = Capability(
            job_id=job_id,
            name=data.name,
            description=data.description,
            importance=importance_value,
        )
        session.add(capability)
        created_capabilities.append(capability)

    await session.commit()
    for cap in created_capabilities:
        await session.refresh(cap)

    return created_capabilities


async def list_capabilities(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> Sequence[Capability] | None:
    job = await get_job_for_organization(session, job_id, organization_id)
    if job is None:
        return None

    result = await session.scalars(
        select(Capability)
        .where(Capability.job_id == job_id)
        .order_by(Capability.created_at.asc())
    )
    return result.all()


async def update_capability(
    session: AsyncSession,
    capability_id: UUID,
    organization_id: UUID,
    data: CapabilityUpdate,
) -> Capability | None:
    capability = await session.scalar(
        select(Capability)
        .join(Job, Capability.job_id == Job.id)
        .where(
            Capability.id == capability_id,
            Job.organization_id == organization_id,
        )
    )
    if capability is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "importance" and isinstance(value, CapabilityImportance):
            value = value.value
        setattr(capability, field, value)

    await session.commit()
    await session.refresh(capability)
    return capability


async def delete_capability(
    session: AsyncSession,
    capability_id: UUID,
    organization_id: UUID,
) -> bool:
    capability = await session.scalar(
        select(Capability)
        .join(Job, Capability.job_id == Job.id)
        .where(
            Capability.id == capability_id,
            Job.organization_id == organization_id,
        )
    )
    if capability is None:
        return False

    await session.delete(capability)
    await session.commit()
    return True
