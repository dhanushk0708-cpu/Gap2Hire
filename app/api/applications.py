from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
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
from app.schemas.evidence import ApplicationEvidenceSummary, EvidenceResponse
from app.services.ai_evidence import AIEvidenceServiceError
from app.services.application import (
    ApplicationNotFoundError,
    CandidateNotFoundError,
    DuplicateApplicationError,
    FileEmptyError,
    FileTooLargeError,
    InvalidFileTypeError,
    JobNotFoundError,
    NoResumeUploadedError,
    ResumeFileNotFoundError,
    create_application,
    get_application_by_id,
    list_applications,
    process_application_resume,
    save_application_resume,
    update_application,
)
from app.services.evidence import (
    NoApprovedCapabilitiesError,
    NoProcessedResumeError,
    analyze_application_evidence,
    get_application_evidence_summary,
)
from app.services.resume_processor import NoExtractableTextError

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


@router.post(
    "/{application_id}/resume",
    response_model=ApplicationResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_application_resume(
    application_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(require_application_manager),
    session: AsyncSession = Depends(get_db_session),
):
    contents = await file.read()
    try:
        return await save_application_resume(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
            file_bytes=contents,
            original_filename=file.filename,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (InvalidFileTypeError, FileEmptyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except FileTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(e),
        ) from e


@router.post(
    "/{application_id}/resume/process",
    response_model=ApplicationResponse,
    status_code=status.HTTP_200_OK,
)
async def process_resume_text(
    application_id: UUID,
    current_user: User = Depends(require_application_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await process_application_resume(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
        )
    except (ApplicationNotFoundError, ResumeFileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (NoResumeUploadedError, NoExtractableTextError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/{application_id}/evidence/analyze",
    response_model=list[EvidenceResponse],
    status_code=status.HTTP_200_OK,
)
async def analyze_evidence_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_application_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await analyze_application_evidence(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (NoProcessedResumeError, NoApprovedCapabilitiesError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except AIEvidenceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.get(
    "/{application_id}/evidence/summary",
    response_model=ApplicationEvidenceSummary,
    status_code=status.HTTP_200_OK,
)
async def get_evidence_summary_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_application_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_application_evidence_summary(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
