from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateUpdate
from app.services.candidate import (
    create_candidate,
    get_candidate_by_id,
    update_candidate,
)

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Candidates"],
)

require_candidate_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_candidate(
    data: CandidateCreate,
    current_user: User = Depends(require_candidate_manager),
    session: AsyncSession = Depends(get_db_session),
):
    return await create_candidate(session=session, data=data)


@router.get(
    "/{candidate_id}",
    response_model=CandidateResponse,
)
async def get_candidate(
    candidate_id: UUID,
    current_user: User = Depends(require_candidate_manager),
    session: AsyncSession = Depends(get_db_session),
):
    candidate = await get_candidate_by_id(
        session=session,
        candidate_id=candidate_id,
        organization_id=current_user.organization_id,
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return candidate


@router.patch(
    "/{candidate_id}",
    response_model=CandidateResponse,
)
async def update_existing_candidate(
    candidate_id: UUID,
    data: CandidateUpdate,
    current_user: User = Depends(require_candidate_manager),
    session: AsyncSession = Depends(get_db_session),
):
    candidate = await update_candidate(
        session=session,
        candidate_id=candidate_id,
        organization_id=current_user.organization_id,
        data=data,
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return candidate
