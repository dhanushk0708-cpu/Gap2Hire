from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.schemas.demo_import import DemoImportResult
from app.services.application import JobNotFoundError
from app.services.demo_import import (
    DemoImportSecurityError,
    InvalidZipArchiveError,
    import_demo_resumes_zip,
)

router = APIRouter(prefix="/api/v1/demo", tags=["Development & Demo Validation"])

require_reviewer = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "/import-resumes",
    response_model=DemoImportResult,
    status_code=status.HTTP_200_OK,
)
async def import_demo_resumes_endpoint(
    file: UploadFile = File(...),
    job_id: UUID = Form(...),
    current_user: User = Depends(require_reviewer),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Demo/Validation endpoint: Ingests a ZIP of synthetic PDF resumes and feeds them
    through candidate creation, URL discovery, grounded evidence extraction, and
    preliminary screening without touching real Gmail candidate pipelines.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename",
        )

    try:
        content = await file.read()
        return await import_demo_resumes_zip(
            session=session,
            organization_id=current_user.organization_id,
            job_id=job_id,
            zip_bytes=content,
            original_filename=file.filename,
        )
    except InvalidZipArchiveError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except DemoImportSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except JobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during demo import: {str(e)}",
        ) from e
