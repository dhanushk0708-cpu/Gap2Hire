from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.job import Job
from app.schemas.interview_analysis import (
    InterviewReport,
    PostInterviewRoundSummary,
)
from app.services.interview import InterviewSessionNotFoundError
from app.services.interview_graph import get_interview_graph
from app.services.interview_pre_analysis import build_pre_interview_analysis


async def get_interview_state(session_id: UUID) -> dict:
    config = {"configurable": {"thread_id": str(session_id)}}
    graph = await get_interview_graph()
    state_snap = await graph.aget_state(config)
    if state_snap and state_snap.values:
        return state_snap.values
    return {}


async def build_interview_report(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
) -> InterviewReport:
    stmt = (
        select(InterviewSession)
        .join(Application, Application.id == InterviewSession.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            InterviewSession.id == session_id,
            Job.organization_id == organization_id,
        )
        .options(
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.messages),
        )
    )
    interview_session = await session.scalar(stmt)
    if interview_session is None:
        raise InterviewSessionNotFoundError("Interview session not found or inaccessible")

    # Get graph state if available
    graph_state = await get_interview_state(session_id)

    # Build pre-interview analysis
    pre_analysis = await build_pre_interview_analysis(
        session=session,
        application_id=interview_session.application_id,
        organization_id=organization_id,
    )

    # Extract round summaries from graph state or construct default
    rounds_raw = graph_state.get("rounds_summary", [])
    rounds_summary = []
    for r in rounds_raw:
        rounds_summary.append(
            PostInterviewRoundSummary(
                round_id=r.get("round_id", "round-1"),
                round_name=r.get("round_name", "Interview Round"),
                round_type=r.get("round_type", "TECHNICAL"),
                sequence=r.get("sequence", 1),
                status=r.get("status", "COMPLETED"),
                capabilities_tested=r.get("capabilities_tested", []),
                questions_asked=r.get("questions_asked", 0),
                followups_used=r.get("followups_used", 0),
                evidence_observed=r.get("evidence_observed", []),
                unknowns_remaining=r.get("unknowns_remaining", []),
            )
        )

    observations = graph_state.get("evidence_observations", [])

    return InterviewReport(
        session_id=interview_session.id,
        application_id=interview_session.application_id,
        job_id=pre_analysis.job_id,
        status=interview_session.status,
        pre_interview_analysis=pre_analysis,
        rounds_summary=rounds_summary,
        evidence_observations=observations,
        total_questions=len(interview_session.questions),
        total_messages=len(interview_session.messages),
        completed_at=interview_session.ended_at,
    )
