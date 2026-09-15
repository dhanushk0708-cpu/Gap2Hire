from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.jd_analysis import JDAnalysisResponse
from app.services.ai_jd import AIServiceError, extract_capabilities_from_jd
from app.services.job import get_job_by_id

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["JD Analysis"],
)

require_jd_analyzer = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "/{job_id}/analyze",
    response_model=JDAnalysisResponse,
)
async def analyze_job_description(
    job_id: UUID,
    current_user: User = Depends(require_jd_analyzer),
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

    try:
        suggested_capabilities = await extract_capabilities_from_jd(
            title=job.title,
            description=job.description,
        )
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return JDAnalysisResponse(
        job_id=job.id,
        suggested_capabilities=suggested_capabilities,
    )
