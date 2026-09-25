from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.candidate_source import (
    CandidateSourceCreate,
    CandidateSourceResponse,
    CandidateSourceUpdate,
)
from app.services.candidate_sources import (
    ApplicationNotFoundError,
    CandidateSourceNotFoundError,
    create_candidate_source,
    get_candidate_source,
    list_candidate_sources,
    update_candidate_source,
)

router = APIRouter(
    tags=["Candidate Sources"],
)

require_source_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "/api/v1/applications/{application_id}/sources",
    response_model=CandidateSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_candidate_source_endpoint(
    application_id: UUID,
    body: CandidateSourceCreate,
    current_user: User = Depends(require_source_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await create_candidate_source(
            session=session,
            organization_id=current_user.organization_id,
            application_id=application_id,
            data=body,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/applications/{application_id}/sources",
    response_model=list[CandidateSourceResponse],
    status_code=status.HTTP_200_OK,
)
async def list_candidate_sources_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_source_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await list_candidate_sources(
            session=session,
            organization_id=current_user.organization_id,
            application_id=application_id,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/candidate-sources/{source_id}",
    response_model=CandidateSourceResponse,
    status_code=status.HTTP_200_OK,
)
async def get_candidate_source_endpoint(
    source_id: UUID,
    current_user: User = Depends(require_source_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_candidate_source(
            session=session,
            organization_id=current_user.organization_id,
            source_id=source_id,
        )
    except CandidateSourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch(
    "/api/v1/candidate-sources/{source_id}",
    response_model=CandidateSourceResponse,
    status_code=status.HTTP_200_OK,
)
async def update_candidate_source_endpoint(
    source_id: UUID,
    body: CandidateSourceUpdate,
    current_user: User = Depends(require_source_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await update_candidate_source(
            session=session,
            organization_id=current_user.organization_id,
            source_id=source_id,
            data=body,
        )
    except CandidateSourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
