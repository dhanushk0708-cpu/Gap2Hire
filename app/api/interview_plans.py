from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.interview_analysis import CandidateInterviewPreAnalysis
from app.schemas.interview_plan import (
    InterviewPlanApprovalRequest,
    InterviewPlanCreateRequest,
    InterviewPlanQuestionSchema,
    InterviewPlanResponse,
    InterviewPlanRoundSchema,
    InterviewPlanUpdateRequest,
)
from app.services.application import ApplicationNotFoundError
from app.services.interview_plan import (
    InterviewPlanNotFoundError,
    InvalidPlanStateError,
    approve_interview_plan,
    generate_candidate_interview_plan,
    get_interview_plan,
    list_candidate_interview_plans,
    update_interview_plan,
)
from app.services.interview_pre_analysis import build_candidate_interview_pre_analysis

router = APIRouter(
    tags=["Interview Plans"],
)

require_hr = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.get(
    "/api/v1/applications/{application_id}/interview/rich-pre-analysis",
    response_model=CandidateInterviewPreAnalysis,
    status_code=status.HTTP_200_OK,
)
async def get_candidate_rich_pre_analysis_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Returns structured candidate pre-interview analysis distinguishing resume CLAIM from
    DEMONSTRATED and VERIFIED capabilities.
    """
    try:
        return await build_candidate_interview_pre_analysis(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/api/v1/applications/{application_id}/interview/plans",
    response_model=InterviewPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_candidate_interview_plan_endpoint(
    application_id: UUID,
    request: InterviewPlanCreateRequest = InterviewPlanCreateRequest(),
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Generates a candidate-specific interview plan based on pre-analysis, evidence,
    unknowns, and HR-uploaded question datasets.
    """
    try:
        plan = await generate_candidate_interview_plan(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
            dataset_file_id=request.dataset_file_id,
            created_by=current_user.id,
        )
        return _format_plan_response(plan)
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/applications/{application_id}/interview/plans",
    response_model=list[InterviewPlanResponse],
    status_code=status.HTTP_200_OK,
)
async def list_candidate_interview_plans_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Lists all historical and current interview plans for a candidate application."""
    plans = await list_candidate_interview_plans(
        session=session,
        application_id=application_id,
        organization_id=current_user.organization_id,
    )
    return [_format_plan_response(p) for p in plans]


@router.get(
    "/api/v1/interview-plans/{plan_id}",
    response_model=InterviewPlanResponse,
    status_code=status.HTTP_200_OK,
)
async def get_interview_plan_endpoint(
    plan_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieves an interview plan with its rounds and questions."""
    try:
        plan = await get_interview_plan(
            session=session,
            organization_id=current_user.organization_id,
            plan_id=plan_id,
        )
        return _format_plan_response(plan)
    except InterviewPlanNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.put(
    "/api/v1/interview-plans/{plan_id}",
    response_model=InterviewPlanResponse,
    status_code=status.HTTP_200_OK,
)
async def update_interview_plan_endpoint(
    plan_id: UUID,
    request: InterviewPlanUpdateRequest,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Allows HR user to edit rounds, objectives, and questions on a draft plan."""
    try:
        plan = await update_interview_plan(
            session=session,
            organization_id=current_user.organization_id,
            plan_id=plan_id,
            data=request,
            updated_by=current_user.id,
        )
        return _format_plan_response(plan)
    except InterviewPlanNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidPlanStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/api/v1/interview-plans/{plan_id}/approve",
    response_model=InterviewPlanResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_interview_plan_endpoint(
    plan_id: UUID,
    request: InterviewPlanApprovalRequest = InterviewPlanApprovalRequest(),
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Approves an interview plan, locking it as an immutable approved plan version."""
    try:
        plan = await approve_interview_plan(
            session=session,
            organization_id=current_user.organization_id,
            plan_id=plan_id,
            approved_by=current_user.id,
            notes=request.notes,
        )
        return _format_plan_response(plan)
    except InterviewPlanNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidPlanStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


def _format_plan_response(plan: Any) -> InterviewPlanResponse:
    rounds_data = []
    for r in plan.rounds:
        questions_data = [
            InterviewPlanQuestionSchema(
                id=q.id,
                dataset_question_id=q.dataset_question_id,
                question_text=q.question_text,
                concept=q.concept,
                difficulty=q.difficulty,
                question_type=q.question_type,
                purpose=q.purpose,
                evidence_being_verified=q.evidence_being_verified,
                sequence=q.sequence,
            )
            for q in r.questions
        ]
        rounds_data.append(
            InterviewPlanRoundSchema(
                id=r.id,
                round_number=r.round_number,
                title=r.title,
                objective=r.objective,
                concepts=r.concepts,
                estimated_duration_minutes=r.estimated_duration_minutes,
                required=r.required,
                reasoning=r.reasoning,
                sequence=r.sequence,
                questions=questions_data,
            )
        )

    return InterviewPlanResponse(
        id=plan.id,
        application_id=plan.application_id,
        job_id=plan.job_id,
        dataset_file_id=plan.dataset_file_id,
        version=plan.version,
        status=plan.status,
        candidate_strengths_summary=plan.candidate_strengths_summary,
        verification_targets_summary=plan.verification_targets_summary,
        hr_feedback=plan.hr_feedback,
        created_by=plan.created_by,
        approved_by=plan.approved_by,
        approved_at=plan.approved_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        rounds=rounds_data,
    )
