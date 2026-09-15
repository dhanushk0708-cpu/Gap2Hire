from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
)
from app.services.application import (
    CandidateNotFoundError,
    DuplicateApplicationError,
    JobNotFoundError,
    create_application,
    get_application_by_id,
    list_applications,
    update_application,
)

router = APIRouter(
    prefix="/api/v1/applications",
    tags=["Applications"],
)

require_application_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_application(
    data: ApplicationCreate,
    current_user: User = Depends(require_application_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await create_application(
            session=session,
            organization_id=current_user.organization_id,
            data=data,
        )
    except CandidateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except JobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except DuplicateApplicationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.get(
    "",
    response_model=list[ApplicationResponse],
)
async def get_all_applications(
    current_user: User = Depends(require_application_manager),
    session: AsyncSession = Depends(get_db_session),
):
    return await list_applications(
        session=session,
        organization_id=current_user.organization_id,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
)
async def get_application(
    application_id: UUID,
    current_user: User = Depends(require_application_manager),
    session: AsyncSession = Depends(get_db_session),
):
    application = await get_application_by_id(
        session=session,
        application_id=application_id,
        organization_id=current_user.organization_id,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return application


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
)
async def update_existing_application(
    application_id: UUID,
    data: ApplicationUpdate,
    current_user: User = Depends(require_application_manager),
    session: AsyncSession = Depends(get_db_session),
):
    application = await update_application(
        session=session,
        application_id=application_id,
        organization_id=current_user.organization_id,
        data=data,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return application
