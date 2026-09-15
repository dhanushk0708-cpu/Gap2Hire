from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.capability import (
    CapabilityBatchCreate,
    CapabilityCreate,
    CapabilityResponse,
    CapabilityUpdate,
)
from app.services.capability import (
    create_capabilities_batch,
    create_capability,
    delete_capability,
    list_capabilities,
    update_capability,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Capabilities"],
)

require_capability_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "/jobs/{job_id}/capabilities",
    response_model=CapabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_capability_to_job(
    job_id: UUID,
    data: CapabilityCreate,
    current_user: User = Depends(require_capability_manager),
    session: AsyncSession = Depends(get_db_session),
):
    capability = await create_capability(
        session=session,
        job_id=job_id,
        organization_id=current_user.organization_id,
        data=data,
    )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return capability


@router.post(
    "/jobs/{job_id}/capabilities/batch",
    response_model=list[CapabilityResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_capabilities_batch_to_job(
    job_id: UUID,
    data: CapabilityBatchCreate,
    current_user: User = Depends(require_capability_manager),
    session: AsyncSession = Depends(get_db_session),
):
    capabilities = await create_capabilities_batch(
        session=session,
        job_id=job_id,
        organization_id=current_user.organization_id,
        capabilities_data=data.capabilities,
    )
    if capabilities is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return capabilities


@router.get(
    "/jobs/{job_id}/capabilities",
    response_model=list[CapabilityResponse],
)
async def get_job_capabilities(
    job_id: UUID,
    current_user: User = Depends(require_capability_manager),
    session: AsyncSession = Depends(get_db_session),
):
    capabilities = await list_capabilities(
        session=session,
        job_id=job_id,
        organization_id=current_user.organization_id,
    )
    if capabilities is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return capabilities


@router.patch(
    "/capabilities/{capability_id}",
    response_model=CapabilityResponse,
)
async def update_existing_capability(
    capability_id: UUID,
    data: CapabilityUpdate,
    current_user: User = Depends(require_capability_manager),
    session: AsyncSession = Depends(get_db_session),
):
    capability = await update_capability(
        session=session,
        capability_id=capability_id,
        organization_id=current_user.organization_id,
        data=data,
    )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capability not found",
        )
    return capability


@router.delete(
    "/capabilities/{capability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_existing_capability(
    capability_id: UUID,
    current_user: User = Depends(require_capability_manager),
    session: AsyncSession = Depends(get_db_session),
):
    deleted = await delete_capability(
        session=session,
        capability_id=capability_id,
        organization_id=current_user.organization_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capability not found",
        )
    return None
