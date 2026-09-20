from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.interview_question_template import (
    InterviewQuestionTemplateCreate,
    InterviewQuestionTemplateResponse,
    InterviewQuestionTemplateUpdate,
)
from app.schemas.interview_round import (
    InterviewRoundCreate,
    InterviewRoundDetailResponse,
    InterviewRoundResponse,
    InterviewRoundUpdate,
)
from app.services.interview_round import (
    DuplicateSequenceError,
    InvalidCapabilityForJobError,
    JobNotFoundError,
    QuestionTemplateNotFoundError,
    RoundNotFoundError,
    create_interview_round,
    create_question_template,
    delete_interview_round,
    delete_question_template,
    get_interview_round_by_id,
    list_interview_rounds_for_job,
    list_question_templates_for_round,
    update_interview_round,
    update_question_template,
)

router = APIRouter(
    tags=["Interview Rounds"],
)

require_hr = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "/api/v1/jobs/{job_id}/interview-rounds",
    response_model=InterviewRoundResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_round_endpoint(
    job_id: UUID,
    round_in: InterviewRoundCreate,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await create_interview_round(
            session=session,
            job_id=job_id,
            round_in=round_in,
            organization_id=current_user.organization_id,
        )
    except JobNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DuplicateSequenceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/api/v1/jobs/{job_id}/interview-rounds",
    response_model=list[InterviewRoundResponse],
    status_code=status.HTTP_200_OK,
)
async def list_rounds_endpoint(
    job_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await list_interview_rounds_for_job(
            session=session,
            job_id=job_id,
            organization_id=current_user.organization_id,
        )
    except JobNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/api/v1/interview-rounds/{round_id}",
    response_model=InterviewRoundDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_round_endpoint(
    round_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    round_obj = await get_interview_round_by_id(
        session=session,
        round_id=round_id,
        organization_id=current_user.organization_id,
    )
    if round_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview round not found")
    return round_obj


@router.patch(
    "/api/v1/interview-rounds/{round_id}",
    response_model=InterviewRoundResponse,
    status_code=status.HTTP_200_OK,
)
async def update_round_endpoint(
    round_id: UUID,
    round_in: InterviewRoundUpdate,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await update_interview_round(
            session=session,
            round_id=round_id,
            round_in=round_in,
            organization_id=current_user.organization_id,
        )
    except RoundNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DuplicateSequenceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/api/v1/interview-rounds/{round_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_round_endpoint(
    round_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        await delete_interview_round(
            session=session,
            round_id=round_id,
            organization_id=current_user.organization_id,
        )
    except RoundNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# --- Question Template Endpoints ---

@router.post(
    "/api/v1/interview-rounds/{round_id}/question-templates",
    response_model=InterviewQuestionTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_question_template_endpoint(
    round_id: UUID,
    template_in: InterviewQuestionTemplateCreate,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await create_question_template(
            session=session,
            round_id=round_id,
            template_in=template_in,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
        )
    except RoundNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InvalidCapabilityForJobError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except DuplicateSequenceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/api/v1/interview-rounds/{round_id}/question-templates",
    response_model=list[InterviewQuestionTemplateResponse],
    status_code=status.HTTP_200_OK,
)
async def list_question_templates_endpoint(
    round_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await list_question_templates_for_round(
            session=session,
            round_id=round_id,
            organization_id=current_user.organization_id,
        )
    except RoundNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.patch(
    "/api/v1/interview-question-templates/{template_id}",
    response_model=InterviewQuestionTemplateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_question_template_endpoint(
    template_id: UUID,
    template_in: InterviewQuestionTemplateUpdate,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await update_question_template(
            session=session,
            template_id=template_id,
            template_in=template_in,
            organization_id=current_user.organization_id,
        )
    except QuestionTemplateNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InvalidCapabilityForJobError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except DuplicateSequenceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/api/v1/interview-question-templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_question_template_endpoint(
    template_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        await delete_question_template(
            session=session,
            template_id=template_id,
            organization_id=current_user.organization_id,
        )
    except QuestionTemplateNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/api/v1/jobs/{job_id}/suggest-questions",
    status_code=status.HTTP_200_OK,
)
async def suggest_questions_for_job_endpoint(
    job_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Generates structured AI question suggestions for all approved capabilities of the job."""
    from app.models.capability import Capability
    from sqlalchemy import select

    caps_stmt = select(Capability).where(Capability.job_id == job_id)
    capabilities = list((await session.scalars(caps_stmt)).all())

    suggestions = []
    for cap in capabilities:
        cap_name = cap.name
        # Build contextual questions per capability
        suggestions.append({
            "capability_id": str(cap.id),
            "capability_name": cap_name,
            "question_intent": "EXPERIENCE",
            "difficulty": "MEDIUM",
            "question_text": f"Can you describe a production project where you utilized {cap_name}, and explain the core architectural decisions you made?",
            "is_ai_suggested": True,
            "max_followups": 2,
        })
        suggestions.append({
            "capability_id": str(cap.id),
            "capability_name": cap_name,
            "question_intent": "DEBUGGING",
            "difficulty": "HARD",
            "question_text": f"How would you diagnose and resolve a severe performance or reliability issue involving {cap_name} under heavy concurrency?",
            "is_ai_suggested": True,
            "max_followups": 2,
        })

    return {"job_id": str(job_id), "suggested_questions": suggestions}

