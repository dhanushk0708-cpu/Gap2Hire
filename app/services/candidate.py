from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.schemas.candidate import CandidateCreate, CandidateUpdate


async def create_candidate(
    session: AsyncSession,
    data: CandidateCreate,
) -> Candidate:
    candidate = Candidate(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)
    return candidate


async def get_candidate_by_id(
    session: AsyncSession,
    candidate_id: UUID,
    organization_id: UUID,
) -> Candidate | None:
    # First check if candidate exists
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        return None

    # Check if candidate has any applications total
    app_count_stmt = select(Application.id).where(Application.candidate_id == candidate_id)
    has_any_apps = (await session.scalars(app_count_stmt)).first() is not None

    if not has_any_apps:
        # Candidate has no applications anywhere yet (e.g. freshly created candidate)
        return candidate

    # If candidate has applications, check if at least one belongs to user's organization
    org_app_stmt = (
        select(Candidate)
        .join(Application, Application.candidate_id == Candidate.id)
        .join(Job, Job.id == Application.job_id)
        .where(
            Candidate.id == candidate_id,
            Job.organization_id == organization_id,
        )
    )
    return await session.scalar(org_app_stmt)


async def update_candidate(
    session: AsyncSession,
    candidate_id: UUID,
    organization_id: UUID,
    data: CandidateUpdate,
) -> Candidate | None:
    candidate = await get_candidate_by_id(session, candidate_id, organization_id)
    if candidate is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(candidate, field, value)

    await session.commit()
    await session.refresh(candidate)
    return candidate
