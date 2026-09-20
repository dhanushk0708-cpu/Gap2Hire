from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewQuestionResponse,
    InterviewSessionDetailResponse,
    InterviewSessionResponse,
)
from app.schemas.interview_analysis import InterviewReport
from app.schemas.interview_avatar import InterviewAvatarMetadata
from app.services.ai_interview import AIInterviewError
from app.services.application import ApplicationNotFoundError
from app.services.interview import (
    CandidateNotShortlistedError,
    InterviewQuestionNotFoundError,
    InterviewSessionNotFoundError,
    InvalidSessionStateError,
    NoApprovedCapabilitiesError,
    QuestionAlreadyAnsweredError,
    create_interview_session,
    generate_next_question_for_session,
    get_tenant_interview_session,
    start_interview_session,
    submit_interview_answer,
)
from app.services.interview_avatar import get_default_avatar_metadata
from app.services.interview_report import build_interview_report, get_interview_state


router = APIRouter(
    tags=["Interviews"],
)

require_interview_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "/api/v1/applications/{application_id}/interviews",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_interview_session_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await create_interview_session(
            session=session,
            application_id=application_id,
            organization_id=current_user.organization_id,
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CandidateNotShortlistedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except NoApprovedCapabilitiesError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/applications/{application_id}/interviews",
    response_model=list[InterviewSessionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_application_interviews_endpoint(
    application_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    from app.models.interview import InterviewSession
    from app.models.application import Application
    from app.models.job import Job

    stmt = (
        select(InterviewSession)
        .join(Application, Application.id == InterviewSession.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == current_user.organization_id,
        )
        .order_by(InterviewSession.created_at.desc())
    )
    return list((await session.scalars(stmt)).all())


@router.patch(
    "/api/v1/interviews/{session_id}/start",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def start_interview_session_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await start_interview_session(
            session=session,
            session_id=session_id,
            organization_id=current_user.organization_id,
        )
    except InterviewSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CandidateNotShortlistedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except InvalidSessionStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/api/v1/interviews/{session_id}/next-question",
    response_model=InterviewQuestionResponse,
    status_code=status.HTTP_200_OK,
)
async def next_question_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await generate_next_question_for_session(
            session=session,
            session_id=session_id,
            organization_id=current_user.organization_id,
        )
    except InterviewSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (InvalidSessionStateError, NoApprovedCapabilitiesError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except AIInterviewError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.post(
    "/api/v1/interviews/{session_id}/questions/{question_id}/answer",
    response_model=InterviewQuestionResponse,
    status_code=status.HTTP_200_OK,
)
async def answer_question_endpoint(
    session_id: UUID,
    question_id: UUID,
    body: InterviewAnswerRequest,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await submit_interview_answer(
            session=session,
            session_id=session_id,
            question_id=question_id,
            answer_text=body.answer,
            organization_id=current_user.organization_id,
        )
    except (InterviewSessionNotFoundError, InterviewQuestionNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (InvalidSessionStateError, QuestionAlreadyAnsweredError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


class LiveCandidateAnswerPayload(BaseModel):
    answer_text: str | None = None
    answer: str | None = None
    content: str | None = None


@router.post(
    "/api/v1/interviews/{session_id}/answers",
    status_code=status.HTTP_200_OK,
)
async def submit_live_answer_endpoint(
    session_id: UUID,
    body: LiveCandidateAnswerPayload,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    from app.services.interview import process_live_candidate_message

    text = (body.answer_text or body.answer or body.content or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Answer text cannot be empty")

    try:
        res = await process_live_candidate_message(
            session=session,
            session_id=session_id,
            candidate_text=text,
            organization_id=current_user.organization_id,
        )
        return {
            "status": "IN_PROGRESS",
            "ai_response": res.content,
            "capability": res.target_capability,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/api/v1/interviews/{session_id}/complete",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def complete_interview_session_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    interview_session = await get_tenant_interview_session(
        session, session_id, current_user.organization_id
    )
    if interview_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )
    interview_session.status = "COMPLETED"
    interview_session.ended_at = datetime.utcnow()
    await session.commit()
    await session.refresh(interview_session)
    return interview_session


@router.get(
    "/api/v1/interviews/{session_id}",
    response_model=InterviewSessionDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_interview_session_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    interview_session = await get_tenant_interview_session(
        session=session,
        session_id=session_id,
        organization_id=current_user.organization_id,
    )
    if interview_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )
    return interview_session


@router.get(
    "/api/v1/interviews/{session_id}/avatar",
    response_model=InterviewAvatarMetadata,
    status_code=status.HTTP_200_OK,
)
async def get_interview_avatar_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    interview_session = await get_tenant_interview_session(
        session=session,
        session_id=session_id,
        organization_id=current_user.organization_id,
    )
    if interview_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )
    return get_default_avatar_metadata()


@router.get(
    "/api/v1/interviews/{session_id}/state",
    status_code=status.HTTP_200_OK,
)
async def get_interview_session_state_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    interview_session = await get_tenant_interview_session(
        session=session,
        session_id=session_id,
        organization_id=current_user.organization_id,
    )
    if interview_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )
    return await get_interview_state(session_id)


@router.get(
    "/api/v1/interviews/{session_id}/hr-live",
    status_code=status.HTTP_200_OK,
)
async def get_hr_live_interview_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    """Read-only live interview observation endpoint for authorized HR / Hiring Managers."""
    from app.models.application import Application
    from app.models.interview import InterviewSession
    from app.models.job import Job

    stmt = (
        select(InterviewSession)
        .join(Application, Application.id == InterviewSession.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            InterviewSession.id == session_id,
            Job.organization_id == current_user.organization_id,
        )
        .options(
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.messages),
            selectinload(InterviewSession.application).selectinload(Application.candidate),
            selectinload(InterviewSession.application).selectinload(Application.job),
        )
    )
    interview_session = await session.scalar(stmt)
    if interview_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found or inaccessible",
        )

    cand_name = interview_session.application.candidate.full_name if interview_session.application and interview_session.application.candidate else "Candidate"
    cand_email = interview_session.application.candidate.email if interview_session.application and interview_session.application.candidate else ""
    job_title = interview_session.application.job.title if interview_session.application and interview_session.application.job else "Position"

    questions = sorted(interview_session.questions, key=lambda q: q.created_at)
    messages = sorted(interview_session.messages, key=lambda m: m.sequence_number)
    current_q = questions[-1] if questions else None

    # Get LangGraph / verification state if available
    graph_state = {}
    try:
        graph_state = await get_interview_state(session_id)
    except Exception:
        pass

    return {
        "session_id": str(interview_session.id),
        "candidate_name": cand_name,
        "candidate_email": cand_email,
        "job_title": job_title,
        "status": interview_session.status,
        "round_number": 1,
        "current_question": current_q.question if current_q else None,
        "candidate_answer": current_q.answer if current_q else None,
        "total_questions": len(questions),
        "transcript_messages": [
            {
                "role": m.role,
                "content": m.content,
                "sequence": m.sequence_number,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "graph_state": graph_state,
        "is_read_only": True,
        "observer_user_id": str(current_user.id),
    }


@router.get(
    "/api/v1/interviews/{session_id}/report",
    response_model=InterviewReport,
    status_code=status.HTTP_200_OK,
)
async def get_interview_session_report_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_interview_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await build_interview_report(
            session=session,
            session_id=session_id,
            organization_id=current_user.organization_id,
        )
    except InterviewSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e




