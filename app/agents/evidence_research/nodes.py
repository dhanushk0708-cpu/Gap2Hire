import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.evidence_research.prompts import (
    extract_evidence_from_source,
    generate_research_decision,
)
from app.agents.evidence_research.state import EvidenceResearchState
from app.agents.evidence_research.tools import (
    discover_candidate_links_impl,
    inspect_candidate_source_impl,
)
from app.core.config import settings
from app.db.session import async_session_factory
from app.models.application import Application
from app.models.candidate_source import CandidateSource
from app.models.capability import Capability
from app.models.job import Job
from app.models.research_capability import ResearchCapabilityState
from app.models.research_session import ResearchSession
from app.services.evidence import record_candidate_evidence
from app.services.research_state import (
    create_research_event,
    update_capability_state,
    update_research_session,
)

logger = logging.getLogger(__name__)


async def load_context_node(state: EvidenceResearchState) -> dict[str, Any]:
    """
    Node 1: Loads all database context under tenant isolation:
    application, job requirements, capabilities, existing capability states, and candidate sources.
    """
    sess_uuid = UUID(state["research_session_id"])
    org_uuid = UUID(state["organization_id"])

    async with async_session_factory() as session:
        stmt = (
            select(ResearchSession)
            .join(Application, Application.id == ResearchSession.application_id)
            .join(Job, Job.id == Application.job_id)
            .where(
                ResearchSession.id == sess_uuid,
                Job.organization_id == org_uuid,
            )
            .options(
                selectinload(ResearchSession.application).selectinload(Application.job),
                selectinload(ResearchSession.capability_states),
            )
        )
        res_session = await session.scalar(stmt)
        if res_session is None:
            return {"status": "FAILED", "error": f"ResearchSession {sess_uuid} not found for tenant"}

        app_obj = res_session.application
        job_obj = app_obj.job

        # Load capabilities for this job
        caps_stmt = select(Capability).where(Capability.job_id == job_obj.id)
        caps = (await session.scalars(caps_stmt)).all()

        # Load candidate sources for this application
        srcs_stmt = select(CandidateSource).where(CandidateSource.application_id == app_obj.id)
        sources = (await session.scalars(srcs_stmt)).all()

        capabilities_list = [
            {"id": str(c.id), "name": c.name, "description": c.description or ""}
            for c in caps
        ]

        capability_states_map = {
            str(cs.capability_id): cs.state for cs in res_session.capability_states
        }

        # Ensure all capabilities are represented in map
        for c in caps:
            if str(c.id) not in capability_states_map:
                capability_states_map[str(c.id)] = "UNKNOWN"

        sources_list = [
            {
                "id": str(s.id),
                "url": s.url,
                "source_type": s.source_type,
                "status": s.status,
                "title": s.title,
                "discovery_depth": s.discovery_depth,
            }
            for s in sources
        ]

        # Update research session status to RUNNING in database
        res_session.status = "RUNNING"
        res_session.last_activity_at = datetime.utcnow()
        await session.commit()

    return {
        "application_id": str(app_obj.id),
        "job_id": str(job_obj.id),
        "job_title": job_obj.title,
        "job_description": job_obj.description or "",
        "capabilities": capabilities_list,
        "capability_states": capability_states_map,
        "candidate_sources": sources_list,
        "inspected_source_ids": [
            s["id"] for s in sources_list if s.get("status") in {"INSPECTED", "FAILED"}
        ],
        "iteration_count": 0,
        "max_iterations": state.get("max_iterations") or settings.max_research_iterations,
        "actions_taken": [],
        "research_findings": [],
        "status": "RUNNING",
    }


async def identify_unresolved_node(state: EvidenceResearchState) -> dict[str, Any]:
    """
    Node 2: Identifies all job capabilities that are not yet SUFFICIENT
    (e.g. UNKNOWN, INVESTIGATING, INSUFFICIENT, VERIFICATION_NEEDED).
    """
    capability_states = state.get("capability_states", {})
    unresolved = [
        cap_id
        for cap_id, st in capability_states.items()
        if st in {"UNKNOWN", "INVESTIGATING", "INSUFFICIENT", "VERIFICATION_NEEDED"}
    ]

    candidate_sources = state.get("candidate_sources", [])
    if not unresolved:
        return {
            "unresolved_capability_ids": [],
            "stop_reason": "All required job capabilities have sufficient evidence.",
        }

    if not candidate_sources:
        return {
            "unresolved_capability_ids": unresolved,
            "stop_reason": "No candidate sources registered for investigation.",
        }

    return {
        "unresolved_capability_ids": unresolved,
    }


async def think_node(state: EvidenceResearchState) -> dict[str, Any]:
    """
    Node 3: Structured LLM reasoning node. Evaluates unresolved capabilities
    and selects the best available candidate source to investigate.
    """
    unresolved_ids = set(state.get("unresolved_capability_ids", []))
    all_caps = state.get("capabilities", [])
    unresolved_caps = [c for c in all_caps if c["id"] in unresolved_ids]

    inspected_set = set(state.get("inspected_source_ids", []))
    available_sources = [
        s for s in state.get("candidate_sources", []) if s["id"] not in inspected_set
    ]

    if not available_sources:
        return {
            "current_decision": None,
            "stop_reason": "All available candidate sources have been inspected.",
        }

    if not unresolved_caps:
        return {
            "current_decision": None,
            "stop_reason": "All capabilities have been resolved.",
        }

    decision = await generate_research_decision(
        job_title=state.get("job_title", ""),
        job_description=state.get("job_description", ""),
        unresolved_capabilities=unresolved_caps,
        available_sources=available_sources,
        actions_taken=state.get("actions_taken", []),
    )

    if decision is None:
        return {
            "current_decision": None,
            "stop_reason": "No further productive source investigations identified.",
        }

    # Verify that the decision selects valid unresolved capability and uninspected source
    valid_cap_ids = {c["id"] for c in unresolved_caps}
    valid_src_ids = {s["id"] for s in available_sources}

    chosen_cap_id = str(decision.capability_id)
    chosen_src_id = str(decision.source_id)

    if chosen_cap_id not in valid_cap_ids or chosen_src_id not in valid_src_ids:
        # Fallback to first available pair
        chosen_cap_id = unresolved_caps[0]["id"]
        chosen_src_id = available_sources[0]["id"]

    return {
        "current_capability_id": chosen_cap_id,
        "current_source_id": chosen_src_id,
        "current_decision": decision.model_dump(),
    }


async def act_node(state: EvidenceResearchState) -> dict[str, Any]:
    """
    Node 4: Executes safe candidate source inspection and link discovery via LangChain tools.
    """
    source_id = state.get("current_source_id")
    org_id = state.get("organization_id")
    app_id = state.get("application_id")
    sess_id = state.get("research_session_id")
    cap_id = state.get("current_capability_id")
    decision = state.get("current_decision", {})

    async with async_session_factory() as session:
        # 1. Inspect source safely
        inspection = await inspect_candidate_source_impl(
            source_id=source_id,
            organization_id=org_id,
            application_id=app_id,
            session=session,
        )

        # 2. If inspection yielded HTML content, discover & register new links
        discovered_info = None
        extracted_text = inspection.get("extracted_text") or ""
        if inspection.get("is_success") and extracted_text:
            discovered_info = await discover_candidate_links_impl(
                source_id=source_id,
                organization_id=org_id,
                application_id=app_id,
                html_content=extracted_text,
                session=session,
            )

        # 3. Log audit event for source selection & inspection
        await create_research_event(
            session=session,
            organization_id=org_id,
            session_id=sess_id,
            event_type="SOURCE_SELECTED",
            source_id=source_id,
            capability_id=cap_id,
            message=f"Selected source {inspection.get('url')} to investigate capability: {decision.get('reason', '')}",
        )

        if inspection.get("is_success"):
            await create_research_event(
                session=session,
                organization_id=org_id,
                session_id=sess_id,
                event_type="SOURCE_INSPECTION_COMPLETED",
                source_id=source_id,
                capability_id=cap_id,
                message=f"Inspected {inspection.get('url')} ({inspection.get('content_length', 0)} bytes).",
            )
        else:
            await create_research_event(
                session=session,
                organization_id=org_id,
                session_id=sess_id,
                event_type="SOURCE_INSPECTION_FAILED",
                source_id=source_id,
                capability_id=cap_id,
                message=f"Failed to inspect {inspection.get('url')}: {inspection.get('error')}",
            )

        if discovered_info and discovered_info.get("new_sources_registered", 0) > 0:
            await create_research_event(
                session=session,
                organization_id=org_id,
                session_id=sess_id,
                event_type="LINKS_DISCOVERED",
                source_id=source_id,
                message=f"Discovered {discovered_info['new_sources_registered']} new candidate sources from page.",
            )

    action_record = {
        "capability_id": cap_id,
        "source_id": source_id,
        "url": inspection.get("url"),
        "is_success": inspection.get("is_success"),
        "reason": decision.get("reason"),
    }

    inspected_ids = list(state.get("inspected_source_ids", []))
    if source_id not in inspected_ids:
        inspected_ids.append(source_id)

    # Refresh candidate_sources if new links were registered
    all_sources = list(state.get("candidate_sources", []))
    if discovered_info and discovered_info.get("discovered_sources"):
        existing_src_ids = {s["id"] for s in all_sources}
        for ds in discovered_info["discovered_sources"]:
            if ds["id"] not in existing_src_ids:
                all_sources.append(ds)

    return {
        "last_observation": inspection,
        "inspected_source_ids": inspected_ids,
        "candidate_sources": all_sources,
        "actions_taken": state.get("actions_taken", []) + [action_record],
    }


async def observe_node(state: EvidenceResearchState) -> dict[str, Any]:
    """
    Node 5: Observes inspection findings and evaluates whether the source provides
    concrete, grounded proof for the capability.
    """
    cap_id = state.get("current_capability_id")
    src_id = state.get("current_source_id")
    all_caps = state.get("capabilities", [])
    all_sources = state.get("candidate_sources", [])
    observation = state.get("last_observation", {})

    cap_obj = next((c for c in all_caps if c["id"] == cap_id), {"id": cap_id, "name": "Capability"})
    src_obj = next((s for s in all_sources if s["id"] == src_id), {"id": src_id, "url": "", "source_type": "OTHER"})

    extraction = await extract_evidence_from_source(
        capability=cap_obj,
        source=src_obj,
        inspection_result=observation,
    )

    return {
        "last_extraction": extraction.model_dump(),
    }


async def update_state_node(state: EvidenceResearchState) -> dict[str, Any]:
    """
    Node 6: Updates durable PostgreSQL business state (creates Evidence with provenance,
    updates ResearchCapabilityState, logs audit events, increments iteration count).
    """
    sess_id = state["research_session_id"]
    org_id = state["organization_id"]
    app_id = state["application_id"]
    cap_id = state["current_capability_id"]
    src_id = state["current_source_id"]
    extraction = state.get("last_extraction", {})
    cap_states = dict(state.get("capability_states", {}))
    findings = list(state.get("research_findings", []))
    all_sources = state.get("candidate_sources", [])
    src_obj = next((s for s in all_sources if s["id"] == src_id), {})

    async with async_session_factory() as session:
        if extraction.get("supported") is True:
            # 1. Create durable Evidence with provenance link to CandidateSource
            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=cap_id,
                source_type=src_obj.get("source_type", "OTHER"),
                strength=extraction.get("strength", "MODERATE"),
                provenance=extraction.get("provenance", "DEMONSTRATED"),
                content=extraction.get("claim"),
                candidate_source_id=src_id,
            )

            # 2. Update ResearchCapabilityState to SUFFICIENT
            await update_capability_state(
                session=session,
                organization_id=org_id,
                session_id=sess_id,
                capability_id=cap_id,
                state="SUFFICIENT",
                reason=extraction.get("explanation"),
            )

            # 3. Log EVIDENCE_FOUND event
            await create_research_event(
                session=session,
                organization_id=org_id,
                session_id=sess_id,
                event_type="EVIDENCE_FOUND",
                source_id=src_id,
                capability_id=cap_id,
                message=extraction.get("claim"),
            )

            cap_states[cap_id] = "SUFFICIENT"
            findings.append({
                "capability_id": cap_id,
                "source_id": src_id,
                "supported": True,
                "claim": extraction.get("claim"),
                "provenance": extraction.get("provenance", "DEMONSTRATED"),
            })

        else:
            # If evidence is not supported, mark state as INSUFFICIENT with explanation
            await update_capability_state(
                session=session,
                organization_id=org_id,
                session_id=sess_id,
                capability_id=cap_id,
                state="INSUFFICIENT",
                reason=extraction.get("explanation"),
            )

            await create_research_event(
                session=session,
                organization_id=org_id,
                session_id=sess_id,
                event_type="CAPABILITY_UPDATED",
                source_id=src_id,
                capability_id=cap_id,
                message=extraction.get("explanation"),
            )

            cap_states[cap_id] = "INSUFFICIENT"
            findings.append({
                "capability_id": cap_id,
                "source_id": src_id,
                "supported": False,
                "explanation": extraction.get("explanation"),
            })

    # Recalculate unresolved capabilities
    unresolved = [
        cid for cid, st in cap_states.items()
        if st in {"UNKNOWN", "INVESTIGATING", "INSUFFICIENT", "VERIFICATION_NEEDED"}
    ]

    new_iteration = state.get("iteration_count", 0) + 1
    max_iter = state.get("max_iterations", 10)

    stop_reason = None
    if not unresolved:
        stop_reason = "All capabilities have sufficient evidence."
    elif new_iteration >= max_iter:
        stop_reason = f"Reached maximum research iteration limit of {max_iter}."

    return {
        "capability_states": cap_states,
        "unresolved_capability_ids": unresolved,
        "research_findings": findings,
        "iteration_count": new_iteration,
        "stop_reason": stop_reason,
    }


# Routing condition functions
def should_start_research(state: EvidenceResearchState) -> str:
    if state.get("stop_reason") is not None or not state.get("unresolved_capability_ids"):
        return "complete"
    return "continue"


def should_act(state: EvidenceResearchState) -> str:
    if state.get("stop_reason") is not None or not state.get("current_decision"):
        return "complete"
    return "act"


def decide_route(state: EvidenceResearchState) -> str:
    if state.get("stop_reason") is not None:
        return "complete"

    unresolved = state.get("unresolved_capability_ids", [])
    if not unresolved:
        return "complete"

    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 10)
    if iteration >= max_iter:
        return "complete"

    inspected_set = set(state.get("inspected_source_ids", []))
    available = [
        s for s in state.get("candidate_sources", []) if s["id"] not in inspected_set
    ]
    if not available:
        return "complete"

    return "think"
