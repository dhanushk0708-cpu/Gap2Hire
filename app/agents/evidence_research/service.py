import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.evidence_research.graph import evidence_research_app
from app.agents.evidence_research.schemas import ResearchRunResult
from app.agents.evidence_research.state import EvidenceResearchState
from app.core.config import settings
from app.db.session import async_session_factory
from app.models.application import Application
from app.models.job import Job
from app.models.research_session import ResearchSession
from app.services.research_state import (
    ResearchSessionNotFoundError,
    create_research_event,
)

logger = logging.getLogger(__name__)


async def run_evidence_research(
    session_id: UUID | str,
    organization_id: UUID | str,
    max_iterations: Optional[int] = None,
) -> ResearchRunResult:
    """
    Executes the LangGraph Evidence Research Agent workflow for a given ResearchSession.

    Validates tenant ownership, updates session lifecycle state, executes the LangGraph
    state machine, logs audit events, and returns a structured execution summary.
    """
    sess_uuid = UUID(str(session_id))
    org_uuid = UUID(str(organization_id))

    # 1. Validate session and tenant ownership
    async with async_session_factory() as db_session:
        stmt = (
            select(ResearchSession)
            .join(Application, Application.id == ResearchSession.application_id)
            .join(Job, Job.id == Application.job_id)
            .where(
                ResearchSession.id == sess_uuid,
                Job.organization_id == org_uuid,
            )
            .options(
                selectinload(ResearchSession.application),
            )
        )
        res_session = await db_session.scalar(stmt)
        if res_session is None:
            raise ResearchSessionNotFoundError(
                f"ResearchSession {session_id} not found for organization {organization_id}"
            )

        app_id = res_session.application_id

        # Mark session as RUNNING and log start event
        res_session.status = "RUNNING"
        res_session.last_activity_at = datetime.utcnow()
        await db_session.commit()

        await create_research_event(
            session=db_session,
            organization_id=org_uuid,
            session_id=sess_uuid,
            event_type="SESSION_STARTED",
            message=f"Starting Evidence Research Agent run for application {app_id}.",
        )

    # 2. Prepare initial graph state
    initial_state: EvidenceResearchState = {
        "research_session_id": str(sess_uuid),
        "organization_id": str(org_uuid),
        "max_iterations": max_iterations or settings.max_research_iterations,
    }

    # 3. Execute LangGraph workflow
    try:
        final_state = await evidence_research_app.ainvoke(initial_state)
    except Exception as e:
        logger.exception(f"Unhandled error during evidence research execution: {e}")
        async with async_session_factory() as db_session:
            stmt = select(ResearchSession).where(ResearchSession.id == sess_uuid)
            db_res = await db_session.scalar(stmt)
            if db_res:
                db_res.status = "FAILED"
                db_res.last_activity_at = datetime.utcnow()
                await db_session.commit()

            await create_research_event(
                session=db_session,
                organization_id=org_uuid,
                session_id=sess_uuid,
                event_type="RESEARCH_FAILED",
                message=f"Agent run failed unexpectedly: {str(e)}",
            )

        return ResearchRunResult(
            research_session_id=sess_uuid,
            application_id=app_id,
            status="FAILED",
            iterations_run=0,
            sources_inspected=0,
            evidence_items_created=0,
            stop_reason=f"Execution error: {str(e)}",
            capability_summary={},
        )

    # 4. Finalize database session state
    is_failed = final_state.get("status") == "FAILED" or bool(final_state.get("error"))
    final_status = "FAILED" if is_failed else "COMPLETED"
    stop_reason = final_state.get("stop_reason") or ("Failed: " + str(final_state.get("error")) if is_failed else "Completed")

    async with async_session_factory() as db_session:
        stmt = select(ResearchSession).where(ResearchSession.id == sess_uuid)
        db_res = await db_session.scalar(stmt)
        if db_res:
            db_res.status = final_status
            db_res.last_activity_at = datetime.utcnow()
            if not is_failed:
                db_res.completed_at = datetime.utcnow()
            await db_session.commit()

        if is_failed:
            await create_research_event(
                session=db_session,
                organization_id=org_uuid,
                session_id=sess_uuid,
                event_type="RESEARCH_FAILED",
                message=f"Research agent failed: {stop_reason}",
            )
        else:
            await create_research_event(
                session=db_session,
                organization_id=org_uuid,
                session_id=sess_uuid,
                event_type="RESEARCH_COMPLETED",
                message=f"Research completed successfully. {stop_reason}",
            )

    findings = final_state.get("research_findings", [])
    evidence_count = len([f for f in findings if f.get("supported") is True])
    inspected_count = len(final_state.get("inspected_source_ids", []))

    return ResearchRunResult(
        research_session_id=sess_uuid,
        application_id=UUID(final_state["application_id"]) if final_state.get("application_id") else app_id,
        status=final_status,
        iterations_run=final_state.get("iteration_count", 0),
        sources_inspected=inspected_count,
        evidence_items_created=evidence_count,
        stop_reason=stop_reason,
        capability_summary=final_state.get("capability_states", {}),
    )
