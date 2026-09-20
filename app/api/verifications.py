from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.verification import (
    VerificationResponse,
    VerificationReview,
    VerificationSubmit,
)
from app.services.verification import (
    InvalidStateTransitionError,
    VerificationNotFoundError,
    cancel_verification,
    review_verification,
    start_verification,
    submit_verification,
)

router = APIRouter(
    prefix="/api/v1/verifications",
    tags=["Verifications"],
)

require_verification_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.patch(
    "/{verification_id}/start",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
)
async def start_verification_endpoint(
    verification_id: UUID,
    current_user: User = Depends(require_verification_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await start_verification(
            session=session,
            verification_id=verification_id,
            organization_id=current_user.organization_id,
        )
    except VerificationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/{verification_id}/submit",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_verification_endpoint(
    verification_id: UUID,
    body: VerificationSubmit,
    current_user: User = Depends(require_verification_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await submit_verification(
            session=session,
            verification_id=verification_id,
            organization_id=current_user.organization_id,
            data=body,
        )
    except VerificationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/{verification_id}/review",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
)
async def review_verification_endpoint(
    verification_id: UUID,
    body: VerificationReview,
    current_user: User = Depends(require_verification_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await review_verification(
            session=session,
            verification_id=verification_id,
            organization_id=current_user.organization_id,
            reviewer_id=current_user.id,
            data=body,
        )
    except VerificationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/{verification_id}/cancel",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_verification_endpoint(
    verification_id: UUID,
    current_user: User = Depends(require_verification_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await cancel_verification(
            session=session,
            verification_id=verification_id,
            organization_id=current_user.organization_id,
        )
    except VerificationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
