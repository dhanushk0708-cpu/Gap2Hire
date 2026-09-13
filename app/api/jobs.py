from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.job import JobCreate, JobResponse, JobUpdate
from app.services.job import (
    create_job,
    delete_job,
    get_job_by_id,
    list_jobs,
    update_job,
)

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["Jobs"],
)

require_job_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_job(
    data: JobCreate,
    current_user: User = Depends(require_job_manager),
    session: AsyncSession = Depends(get_db_session),
):
    return await create_job(
        session=session,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )


@router.get(
    "",
    response_model=list[JobResponse],
)
async def get_all_jobs(
    current_user: User = Depends(require_job_manager),
    session: AsyncSession = Depends(get_db_session),
):
    return await list_jobs(
        session=session,
        organization_id=current_user.organization_id,
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
)
async def get_job(
    job_id: UUID,
    current_user: User = Depends(require_job_manager),
    session: AsyncSession = Depends(get_db_session),
):
    job = await get_job_by_id(
        session=session,
        job_id=job_id,
        organization_id=current_user.organization_id,
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.patch(
    "/{job_id}",
    response_model=JobResponse,
)
async def update_existing_job(
    job_id: UUID,
    data: JobUpdate,
    current_user: User = Depends(require_job_manager),
    session: AsyncSession = Depends(get_db_session),
):
    job = await update_job(
        session=session,
        job_id=job_id,
        organization_id=current_user.organization_id,
        data=data,
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_existing_job(
    job_id: UUID,
    current_user: User = Depends(require_job_manager),
    session: AsyncSession = Depends(get_db_session),
):
    deleted = await delete_job(
        session=session,
        job_id=job_id,
        organization_id=current_user.organization_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return None
