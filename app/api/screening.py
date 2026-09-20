from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.application import Application
from app.models.user import User
from app.schemas.screening import (
    CandidateScreeningResult,
    JobCandidateListItem,
    ScreeningUpdateRequest,
    ShortlistDecisionRequest,
    ShortlistDecisionResponse,
)
from app.services.screening import (
    ApplicationNotFoundError,
    InvalidShortlistDecisionError,
    JobNotFoundError,
    apply_shortlist_decision,
    build_candidate_screening_report,
    list_job_candidates_with_screening,
)

router = APIRouter(tags=["Candidate Screening & Shortlisting"])

require_reviewer = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.get(
    "/api/v1/jobs/{job_id}/candidates",
    response_model=list[JobCandidateListItem],
    status_code=status.HTTP_200_OK,
)
async def get_job_candidates_endpoint(
    job_id: UUID,
    current_user: User = Depends(require_reviewer),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await list_job_candidates_with_screening(
            session=session,
            job_id=job_id,
            organization_id=current_user.organization_id,
        )
    except JobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/jobs/{job_id}/screening-queue",
    response_model=list[JobCandidateListItem],
    status_code=status.HTTP_200_OK,
)
async def get_job_screening_queue_endpoint(
    job_id: UUID,
    current_user: User = Depends(require_reviewer),
    session: AsyncSession = Depends(get_db_session),
):
    """Returns candidate screening queue for a job."""
    return await get_job_candidates_endpoint(
        job_id=job_id,
        current_user=current_user,
        session=session,
    )


@router.post(
    "/api/v1/applications/{application_id}/run-screening",
    response_model=CandidateScreeningResult,
    status_code=status.HTTP_200_OK,
)
async def run_screening_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_reviewer),
    session: AsyncSession = Depends(get_db_session),
):
    """Explicit HR action: 'RUN SCREENING'. Evaluates structured evidence & job requirements deterministically."""
    try:
        report = await build_candidate_screening_report(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
        )
        app_obj = await session.get(Application, application_id)
        if app_obj:
            app_obj.screening_status = report.screening_status
            app_obj.screening_notes = report.summary_explanation
            await session.commit()
        return report
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/applications/{application_id}/screening",
    response_model=CandidateScreeningResult,
    status_code=status.HTTP_200_OK,
)
async def get_candidate_screening_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_reviewer),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await build_candidate_screening_report(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch(
    "/api/v1/applications/{application_id}/screening",
    response_model=CandidateScreeningResult,
    status_code=status.HTTP_200_OK,
)
async def update_candidate_screening_endpoint(
    application_id: UUID,
    body: ScreeningUpdateRequest,
    current_user: User = Depends(require_reviewer),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        # Load application to update screening notes / status
        app_obj = await session.get(Application, application_id)
        if not app_obj:
            raise ApplicationNotFoundError("Application not found")

        app_obj.screening_status = body.screening_status
        if body.screening_notes is not None:
            app_obj.screening_notes = body.screening_notes
        await session.commit()

        return await build_candidate_screening_report(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch(
    "/api/v1/applications/{application_id}/shortlist",
    response_model=ShortlistDecisionResponse,
    status_code=status.HTTP_200_OK,
)
async def shortlist_candidate_endpoint(
    application_id: UUID,
    body: ShortlistDecisionRequest,
    current_user: User = Depends(require_reviewer),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await apply_shortlist_decision(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
            decision=body.decision,
            reason=body.reason,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidShortlistDecisionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
