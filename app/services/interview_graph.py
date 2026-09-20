import asyncio
import logging
import sys
from typing import Any, Literal
from uuid import UUID

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.application import Application
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_round import InterviewQuestionTemplate, InterviewRound
from app.models.job import Job
from app.schemas.interview_state import InterviewState
from app.services.ai_interview_analysis import (
    analyze_candidate_answer,
    frame_question_with_ai,
    generate_adaptive_followup,
)
from app.services.interview_pre_analysis import build_pre_interview_analysis

logger = logging.getLogger(__name__)

_checkpointer = None
_pool = None
_compiled_graph = None


async def get_checkpointer():
    """Initializes PostgreSQL-backed async checkpointer with connection pooling for persistent interview graph states."""
    global _checkpointer, _pool
    if _checkpointer is None:
        try:
            conn_str = str(settings.database_url).replace("+asyncpg", "")
            _pool = AsyncConnectionPool(
                conninfo=conn_str,
                max_size=20,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
                open=False,
            )
            await _pool.open()
            saver = AsyncPostgresSaver(conn=_pool)
            await saver.setup()
            _checkpointer = saver
            logger.info("Successfully initialized PostgreSQL persistent AsyncPostgresSaver pool for LangGraph")
        except Exception as exc:
            logger.warning(f"Could not connect to PostgreSQL checkpointer, falling back to InMemorySaver: {exc}")
            _checkpointer = InMemorySaver()
    return _checkpointer


# --- Node Definitions ---

async def node_load_context(state: InterviewState) -> dict[str, Any]:
    """Loads all static context, rounds, capabilities, and pre-analysis if not already loaded."""
    session_id_str = state.get("session_id", "")
    return {
        "round_status": "IN_PROGRESS",
        "interview_status": "IN_PROGRESS",
        "next_action": "SELECT_ROUND",
    }


async def node_select_round(state: InterviewState) -> dict[str, Any]:
    """Finds the current or next active round in sequence that is not completed."""
    rounds = state.get("rounds_list", [])
    completed_round_ids = {r["round_id"] for r in state.get("rounds_summary", []) if r.get("status") == "COMPLETED"}

    # Find first uncompleted round in sequence
    active_round = None
    for r in sorted(rounds, key=lambda x: x.get("sequence", 1)):
        if r.get("id") not in completed_round_ids:
            active_round = r
            break

    if active_round is None:
        # All rounds completed
        return {
            "current_round_id": None,
            "round_status": "COMPLETED",
            "next_action": "COMPLETE_INTERVIEW",
        }

    return {
        "current_round_id": active_round.get("id"),
        "current_round_type": active_round.get("round_type", "TECHNICAL"),
        "current_round_name": active_round.get("name", "Interview Round"),
        "round_sequence": active_round.get("sequence", 1),
        "round_status": "IN_PROGRESS",
        "next_action": "SELECT_QUESTION",
    }


async def node_select_question(state: InterviewState) -> dict[str, Any]:
    """Selects the next question template for the active round, prioritizing unverified capabilities."""
    current_round_id = state.get("current_round_id")
    rounds = state.get("rounds_list", [])
    asked_template_ids = {q.get("template_id") for q in state.get("questions_asked", []) if q.get("template_id")}

    current_round = next((r for r in rounds if r.get("id") == current_round_id), None)
    if not current_round:
        return {"next_action": "COMPLETE_ROUND"}

    templates = current_round.get("templates", [])
    unasked_templates = [t for t in templates if t.get("id") not in asked_template_ids]

    if not unasked_templates:
        return {"next_action": "COMPLETE_ROUND"}

    # Sort templates: prioritize those targeting capabilities with unverified claims
    claims_to_verify_cap_ids = {c.get("capability_id") for c in state.get("claims_to_verify", [])}

    def template_priority(t: dict) -> int:
        cap_id = t.get("capability_id")
        if cap_id in claims_to_verify_cap_ids:
            return 0  # highest priority
        if cap_id is not None:
            return 1
        return 2  # general round question without capability mapping

    sorted_templates = sorted(unasked_templates, key=lambda t: (template_priority(t), t.get("sequence", 1)))
    selected_template = sorted_templates[0]

    # Resolve capability details
    cap_id = selected_template.get("capability_id")
    capabilities = state.get("capabilities_list", [])
    matched_cap = next((c for c in capabilities if c.get("id") == cap_id), None)
    cap_name = matched_cap.get("name") if matched_cap else "General Knowledge"

    return {
        "current_template_id": selected_template.get("id"),
        "current_question_intent": selected_template.get("question_intent", "KNOWLEDGE"),
        "current_question_text": selected_template.get("question_text", ""),
        "current_capability_id": cap_id,
        "current_capability_name": cap_name,
        "max_followups": selected_template.get("max_followups", 2),
        "follow_up_count": 0,
        "next_action": "FRAME_QUESTION",
    }


async def node_frame_question(state: InterviewState) -> dict[str, Any]:
    """Frames the HR question template into natural AI interview dialogue."""
    template_text = state.get("current_question_text", "")
    capability_name = state.get("current_capability_name", "General")
    intent = state.get("current_question_intent", "KNOWLEDGE")

    framed = await frame_question_with_ai(
        template_text=template_text,
        capability_name=capability_name,
        question_intent=intent,
    )

    questions_asked = list(state.get("questions_asked", []))
    questions_asked.append({
        "template_id": state.get("current_template_id"),
        "capability_id": state.get("current_capability_id"),
        "capability_name": capability_name,
        "intent": intent,
        "question": framed,
        "is_followup": False,
    })

    return {
        "current_framed_question": framed,
        "questions_asked": questions_asked,
        "next_action": "WAIT_FOR_CANDIDATE",
    }


async def node_wait_for_answer(state: InterviewState) -> dict[str, Any]:
    """Pauses graph execution using interrupt, waiting for the candidate answer."""
    question_payload = {
        "question": state.get("current_framed_question"),
        "capability_id": state.get("current_capability_id"),
        "capability_name": state.get("current_capability_name"),
        "intent": state.get("current_question_intent"),
        "round_id": state.get("current_round_id"),
        "round_name": state.get("current_round_name"),
        "follow_up_count": state.get("follow_up_count", 0),
    }

    # Pause execution and return question_payload to caller
    candidate_answer_input = interrupt(question_payload)

    # Resume: parse candidate answer
    if isinstance(candidate_answer_input, dict):
        answer_text = candidate_answer_input.get("answer", "")
    else:
        answer_text = str(candidate_answer_input or "")

    candidate_answers = list(state.get("candidate_answers", []))
    candidate_answers.append({
        "question": state.get("current_framed_question"),
        "answer": answer_text,
        "capability_name": state.get("current_capability_name"),
    })

    return {
        "latest_candidate_answer": answer_text,
        "candidate_answers": candidate_answers,
        "next_action": "ANALYZE_ANSWER",
    }


async def node_analyze_answer(state: InterviewState) -> dict[str, Any]:
    """Analyzes candidate answer against the target capability and checks if follow-up is warranted."""
    question_text = state.get("current_framed_question", "")
    candidate_answer = state.get("latest_candidate_answer", "")
    cap_name = state.get("current_capability_name", "General")
    cap_id = state.get("current_capability_id")
    intent = state.get("current_question_intent", "KNOWLEDGE")
    follow_up_count = state.get("follow_up_count", 0)
    max_followups = state.get("max_followups", 2)

    observation = await analyze_candidate_answer(
        question_text=question_text,
        candidate_answer=candidate_answer,
        capability_name=cap_name,
        capability_id=cap_id,
        question_intent=intent,
        follow_up_count=follow_up_count,
        max_followups=max_followups,
    )

    observations = list(state.get("evidence_observations", []))
    obs_dict = observation.model_dump()
    obs_dict["round_id"] = state.get("current_round_id")
    obs_dict["round_name"] = state.get("current_round_name")
    obs_dict["question"] = question_text
    obs_dict["answer"] = candidate_answer
    observations.append(obs_dict)

    return {
        "answer_analysis": obs_dict,
        "evidence_observations": observations,
    }


async def node_generate_followup(state: InterviewState) -> dict[str, Any]:
    """Generates an adaptive probing follow-up question directly addressing the identified gap."""
    analysis = state.get("answer_analysis", {})
    focus = analysis.get("follow_up_focus") or "elaborate with practical details"
    cap_name = state.get("current_capability_name", "General")
    orig_q = state.get("current_framed_question", "")
    cand_ans = state.get("latest_candidate_answer", "")

    followup_text = await generate_adaptive_followup(
        question_text=orig_q,
        candidate_answer=cand_ans,
        follow_up_focus=focus,
        capability_name=cap_name,
    )

    new_count = state.get("follow_up_count", 0) + 1
    questions_asked = list(state.get("questions_asked", []))
    questions_asked.append({
        "template_id": state.get("current_template_id"),
        "capability_id": state.get("current_capability_id"),
        "capability_name": cap_name,
        "intent": "FOLLOW_UP",
        "question": followup_text,
        "is_followup": True,
        "follow_up_count": new_count,
    })

    return {
        "current_framed_question": followup_text,
        "follow_up_count": new_count,
        "questions_asked": questions_asked,
        "next_action": "WAIT_FOR_CANDIDATE",
    }


async def node_advance_workflow(state: InterviewState) -> dict[str, Any]:
    """Evaluates whether more questions remain in the active round or if the round is complete."""
    current_round_id = state.get("current_round_id")
    rounds = state.get("rounds_list", [])
    asked_template_ids = {q.get("template_id") for q in state.get("questions_asked", []) if q.get("template_id")}

    current_round = next((r for r in rounds if r.get("id") == current_round_id), None)
    if not current_round:
        return {"next_action": "COMPLETE_ROUND"}

    templates = current_round.get("templates", [])
    unasked = [t for t in templates if t.get("id") not in asked_template_ids]

    if unasked:
        return {"next_action": "SELECT_QUESTION"}
    return {"next_action": "COMPLETE_ROUND"}


async def node_complete_round(state: InterviewState) -> dict[str, Any]:
    """Finalizes summary for the current round and advances to the next round if available."""
    current_round_id = state.get("current_round_id")
    current_round_name = state.get("current_round_name", "")
    current_round_type = state.get("current_round_type", "")
    sequence = state.get("round_sequence", 1)

    # Calculate tested capabilities in this round
    round_obs = [o for o in state.get("evidence_observations", []) if o.get("round_id") == current_round_id]
    tested_caps = list({o.get("capability_name") for o in round_obs if o.get("capability_name")})
    questions_count = len([q for q in state.get("questions_asked", []) if not q.get("is_followup")])
    followups_count = len([q for q in state.get("questions_asked", []) if q.get("is_followup")])

    summary = {
        "round_id": current_round_id,
        "round_name": current_round_name,
        "round_type": current_round_type,
        "sequence": sequence,
        "status": "COMPLETED",
        "capabilities_tested": tested_caps,
        "questions_asked": questions_count,
        "followups_used": followups_count,
        "evidence_observed": round_obs,
    }

    rounds_summary = list(state.get("rounds_summary", []))
    rounds_summary.append(summary)

    # Check if more rounds remain
    rounds = state.get("rounds_list", [])
    completed_ids = {s["round_id"] for s in rounds_summary}
    remaining_rounds = [r for r in rounds if r.get("id") not in completed_ids]

    if remaining_rounds:
        return {
            "rounds_summary": rounds_summary,
            "round_status": "COMPLETED",
            "next_action": "SELECT_ROUND",
        }

    return {
        "rounds_summary": rounds_summary,
        "round_status": "COMPLETED",
        "next_action": "COMPLETE_INTERVIEW",
    }


async def node_complete_interview(state: InterviewState) -> dict[str, Any]:
    """Marks entire interview session complete."""
    return {
        "interview_status": "COMPLETED",
        "next_action": "INTERVIEW_COMPLETED",
    }


# --- Routing Decisions ---

def route_after_load(state: InterviewState) -> Literal["select_round"]:
    return "select_round"


def route_after_round_select(state: InterviewState) -> Literal["select_question", "complete_interview"]:
    if state.get("next_action") == "COMPLETE_INTERVIEW" or not state.get("current_round_id"):
        return "complete_interview"
    return "select_question"


def route_after_question_select(state: InterviewState) -> Literal["frame_question", "complete_round"]:
    if state.get("next_action") == "COMPLETE_ROUND":
        return "complete_round"
    return "frame_question"


def route_after_analysis(state: InterviewState) -> Literal["generate_followup", "advance_workflow"]:
    analysis = state.get("answer_analysis") or {}
    follow_up_count = state.get("follow_up_count", 0)
    max_followups = state.get("max_followups", 2)
    if analysis.get("follow_up_needed") and (follow_up_count < max_followups):
        return "generate_followup"
    return "advance_workflow"


def route_after_advance(state: InterviewState) -> Literal["select_question", "complete_round"]:
    if state.get("next_action") == "SELECT_QUESTION":
        return "select_question"
    return "complete_round"


def route_after_round_complete(state: InterviewState) -> Literal["select_round", "complete_interview"]:
    if state.get("next_action") == "SELECT_ROUND":
        return "select_round"
    return "complete_interview"


# --- Graph Construction ---

def build_interview_graph(checkpointer=None):
    builder = StateGraph(InterviewState)

    builder.add_node("load_context", node_load_context)
    builder.add_node("select_round", node_select_round)
    builder.add_node("select_question", node_select_question)
    builder.add_node("frame_question", node_frame_question)
    builder.add_node("wait_for_answer", node_wait_for_answer)
    builder.add_node("analyze_answer", node_analyze_answer)
    builder.add_node("generate_followup", node_generate_followup)
    builder.add_node("advance_workflow", node_advance_workflow)
    builder.add_node("complete_round", node_complete_round)
    builder.add_node("complete_interview", node_complete_interview)

    builder.add_edge(START, "load_context")
    builder.add_conditional_edges("load_context", route_after_load)
    builder.add_conditional_edges("select_round", route_after_round_select)
    builder.add_conditional_edges("select_question", route_after_question_select)
    builder.add_edge("frame_question", "wait_for_answer")
    builder.add_edge("wait_for_answer", "analyze_answer")
    builder.add_conditional_edges("analyze_answer", route_after_analysis)
    builder.add_edge("generate_followup", "wait_for_answer")
    builder.add_conditional_edges("advance_workflow", route_after_advance)
    builder.add_conditional_edges("complete_round", route_after_round_complete)
    builder.add_edge("complete_interview", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


async def get_interview_graph():
    global _compiled_graph
    if _compiled_graph is None:
        cp = await get_checkpointer()
        _compiled_graph = build_interview_graph(checkpointer=cp)
    return _compiled_graph


# --- Database Synchronization & Workflow Orchestrator ---

async def initialize_interview_state_from_db(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
) -> InterviewState:
    """Prepares the initial InterviewState from PostgreSQL records."""
    stmt = (
        select(InterviewSession)
        .join(Application, Application.id == InterviewSession.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            InterviewSession.id == session_id,
            Job.organization_id == organization_id,
        )
    )
    interview_session = await session.scalar(stmt)
    if not interview_session:
        raise ValueError(f"Interview session {session_id} not found or inaccessible")

    app_id = interview_session.application_id
    app_obj = await session.get(Application, app_id)
    job_id = app_obj.job_id

    # 1. Load job capabilities
    caps_stmt = select(Capability).where(Capability.job_id == job_id)
    capabilities = list((await session.scalars(caps_stmt)).all())
    caps_list = [{"id": str(c.id), "name": c.name, "importance": c.importance} for c in capabilities]

    # 2. Load interview rounds and question templates
    rounds_stmt = (
        select(InterviewRound)
        .where(InterviewRound.job_id == job_id, InterviewRound.status == "ACTIVE")
        .options(selectinload(InterviewRound.question_templates))
        .order_by(InterviewRound.sequence.asc())
    )
    rounds_db = list((await session.scalars(rounds_stmt)).all())

    # Fallback if no rounds configured: generate default round & templates from capabilities
    if not rounds_db:
        default_templates = []
        for i, cap in enumerate(capabilities, 1):
            default_templates.append({
                "id": f"default-t-{cap.id}",
                "capability_id": str(cap.id),
                "question_intent": "KNOWLEDGE",
                "question_text": f"Can you explain your experience and depth with {cap.name}?",
                "max_followups": 2,
                "sequence": i,
            })
        rounds_list = [{
            "id": "default-round-1",
            "name": "Technical Assessment",
            "round_type": "TECHNICAL",
            "sequence": 1,
            "templates": default_templates,
        }]
    else:
        rounds_list = []
        for r in rounds_db:
            t_list = []
            for t in sorted(r.question_templates, key=lambda x: x.sequence):
                t_list.append({
                    "id": str(t.id),
                    "capability_id": str(t.capability_id) if t.capability_id else None,
                    "question_intent": t.question_intent,
                    "question_text": t.question_text,
                    "max_followups": t.max_followups,
                    "sequence": t.sequence,
                })
            rounds_list.append({
                "id": str(r.id),
                "name": r.name,
                "round_type": r.round_type,
                "sequence": r.sequence,
                "templates": t_list,
            })

    # 3. Pre-interview analysis
    pre_analysis = await build_pre_interview_analysis(
        session=session,
        application_id=app_id,
        organization_id=organization_id,
    )

    initial_state: InterviewState = {
        "session_id": str(session_id),
        "application_id": str(app_id),
        "job_id": str(job_id),
        "organization_id": str(organization_id),
        "current_round_id": None,
        "current_round_type": None,
        "current_round_name": None,
        "round_sequence": 1,
        "rounds_list": rounds_list,
        "current_capability_id": None,
        "current_capability_name": None,
        "capabilities_list": caps_list,
        "current_template_id": None,
        "current_question_intent": None,
        "current_question_text": None,
        "current_question_id": None,
        "current_framed_question": None,
        "questions_asked": [],
        "candidate_answers": [],
        "evidence_observations": [],
        "claims_to_verify": pre_analysis.claims_to_verify,
        "unknowns_remaining": [u.model_dump() for u in pre_analysis.unknown_capabilities],
        "follow_up_count": 0,
        "max_followups": 2,
        "latest_candidate_answer": None,
        "answer_analysis": None,
        "next_action": "START",
        "round_status": "IN_PROGRESS",
        "interview_status": "IN_PROGRESS",
        "rounds_summary": [],
    }
    return initial_state


async def start_or_resume_interview_graph(
    session_id: UUID,
    db_session: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Runs or resumes the graph until the first/next candidate interaction interrupt."""
    config = {"configurable": {"thread_id": str(session_id)}}
    graph = await get_interview_graph()

    # Check if graph state already exists in checkpointer
    current_snapshot = await graph.aget_state(config)
    if not current_snapshot or not current_snapshot.values:
        init_state = await initialize_interview_state_from_db(
            session=db_session,
            session_id=session_id,
            organization_id=organization_id,
        )
        await graph.ainvoke(init_state, config=config)
    else:
        # Check if tasks are waiting on interrupt
        if not current_snapshot.tasks:
            # Re-run or advance
            await graph.ainvoke(None, config=config)

    # Get updated state & active interrupt
    state_snap = await graph.aget_state(config)
    tasks = state_snap.tasks
    interrupt_payload = None
    if tasks:
        for t in tasks:
            if t.interrupts:
                interrupt_payload = t.interrupts[0].value
                break

    state_values = state_snap.values or {}

    # Synchronize with PostgreSQL InterviewSession
    curr_round_id = state_values.get("current_round_id")
    curr_cap_id = state_values.get("current_capability_id")

    session_obj = await db_session.get(InterviewSession, session_id)
    if session_obj:
        if curr_round_id and UUID(curr_round_id) != session_obj.current_round_id:
            try:
                session_obj.current_round_id = UUID(curr_round_id)
            except Exception:
                pass
        if curr_cap_id:
            try:
                session_obj.current_capability_id = UUID(curr_cap_id)
            except Exception:
                pass
        await db_session.commit()

    return {
        "status": state_values.get("interview_status", "IN_PROGRESS"),
        "question": interrupt_payload.get("question") if isinstance(interrupt_payload, dict) else state_values.get("current_framed_question"),
        "capability": interrupt_payload.get("capability_name") if isinstance(interrupt_payload, dict) else state_values.get("current_capability_name"),
        "capability_id": interrupt_payload.get("capability_id") if isinstance(interrupt_payload, dict) else state_values.get("current_capability_id"),
        "intent": interrupt_payload.get("intent") if isinstance(interrupt_payload, dict) else state_values.get("current_question_intent"),
        "round_name": interrupt_payload.get("round_name") if isinstance(interrupt_payload, dict) else state_values.get("current_round_name"),
        "follow_up_count": interrupt_payload.get("follow_up_count", 0) if isinstance(interrupt_payload, dict) else state_values.get("follow_up_count", 0),
        "interrupt_payload": interrupt_payload,
        "state": state_values,
    }


async def submit_candidate_answer_to_graph(
    session_id: UUID,
    answer_text: str,
    db_session: AsyncSession,
    organization_id: UUID,
) -> dict[str, Any]:
    """Resumes the graph from interrupt with candidate answer and runs until the next question or completion."""
    config = {"configurable": {"thread_id": str(session_id)}}
    graph = await get_interview_graph()

    # Resume graph with answer
    await graph.ainvoke(Command(resume=answer_text), config=config)

    # Get updated snapshot
    state_snap = await graph.aget_state(config)
    state_values = state_snap.values or {}

    tasks = state_snap.tasks
    interrupt_payload = None
    if tasks:
        for t in tasks:
            if t.interrupts:
                interrupt_payload = t.interrupts[0].value
                break

    # Persist in DB: sync questions, messages, observations
    session_obj = await db_session.get(InterviewSession, session_id)
    if session_obj:
        if state_values.get("interview_status") == "COMPLETED":
            session_obj.status = "COMPLETED"

        # Check latest observation and persist as Evidence if high confidence
        latest_analysis = state_values.get("answer_analysis")
        if latest_analysis and latest_analysis.get("capability_id"):
            try:
                cap_uuid = UUID(latest_analysis["capability_id"])
                # Check if evidence record exists
                ev_stmt = select(Evidence).where(
                    Evidence.application_id == session_obj.application_id,
                    Evidence.capability_id == cap_uuid,
                    Evidence.source_type == "INTERVIEW",
                )
                existing_ev = await db_session.scalar(ev_stmt)
                if not existing_ev:
                    new_ev = Evidence(
                        application_id=session_obj.application_id,
                        capability_id=cap_uuid,
                        source_type="INTERVIEW",
                        content=latest_analysis.get("observation", "Interview evidence observed"),
                        strength="STRONG" if latest_analysis.get("confidence") == "HIGH" else "MODERATE",
                        provenance="INTERVIEW",
                    )
                    db_session.add(new_ev)
                else:
                    existing_ev.content = latest_analysis.get("observation", existing_ev.content)
            except Exception as exc:
                logger.warning(f"Error persisting interview evidence: {exc}")

        await db_session.commit()

    return {
        "status": state_values.get("interview_status", "IN_PROGRESS"),
        "round_status": state_values.get("round_status", "IN_PROGRESS"),
        "question": interrupt_payload.get("question") if isinstance(interrupt_payload, dict) else state_values.get("current_framed_question"),
        "capability": interrupt_payload.get("capability_name") if isinstance(interrupt_payload, dict) else state_values.get("current_capability_name"),
        "capability_id": interrupt_payload.get("capability_id") if isinstance(interrupt_payload, dict) else state_values.get("current_capability_id"),
        "intent": interrupt_payload.get("intent") if isinstance(interrupt_payload, dict) else state_values.get("current_question_intent"),
        "round_name": interrupt_payload.get("round_name") if isinstance(interrupt_payload, dict) else state_values.get("current_round_name"),
        "follow_up_count": interrupt_payload.get("follow_up_count", 0) if isinstance(interrupt_payload, dict) else state_values.get("follow_up_count", 0),
        "is_followup": bool(interrupt_payload.get("follow_up_count", 0) > 0) if isinstance(interrupt_payload, dict) else False,
        "is_interview_completed": state_values.get("interview_status") == "COMPLETED",
        "state": state_values,
    }
