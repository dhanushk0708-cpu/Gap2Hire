import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_round import InterviewRound
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.interview_ws import WSAIMessageEvent
from app.services.ai_interview import generate_interview_question, generate_live_ai_response
from app.services.application import ApplicationNotFoundError

logger = logging.getLogger(__name__)


class InterviewSessionNotFoundError(Exception):
    pass


class InterviewQuestionNotFoundError(Exception):
    pass


class InvalidSessionStateError(Exception):
    pass


class QuestionAlreadyAnsweredError(Exception):
    pass


class NoApprovedCapabilitiesError(Exception):
    pass


class CandidateNotShortlistedError(Exception):
    pass


async def get_tenant_interview_session(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
) -> InterviewSession | None:
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
    return await session.scalar(stmt)


async def create_interview_session(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> InterviewSession:
    app_stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(app_stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found")

    if (
        application.status == "NOT_SHORTLISTED"
        or application.shortlist_status in ("NOT_SHORTLISTED", "HOLD")
        or (application.shortlist_status == "PENDING" and application.status in ("SCREENING", "RECEIVED", "HOLD", "NOT_SHORTLISTED"))
    ):
        raise CandidateNotShortlistedError(
            f"Cannot create interview session: Candidate is not shortlisted ({application.shortlist_status or application.status})."
        )

    caps_stmt = select(Capability).where(Capability.job_id == application.job_id)
    capabilities = (await session.scalars(caps_stmt)).all()
    if not capabilities:
        raise NoApprovedCapabilitiesError("Job has no approved capabilities for an interview")

    interview_session = InterviewSession(
        application_id=application.id,
        status="CREATED",
    )
    session.add(interview_session)
    await session.commit()
    await session.refresh(interview_session)
    return interview_session


async def start_interview_session(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
) -> InterviewSession:
    interview_session = await get_tenant_interview_session(
        session, session_id, organization_id
    )
    if interview_session is None:
        raise InterviewSessionNotFoundError("Interview session not found")

    if interview_session.status != "CREATED":
        raise InvalidSessionStateError(
            f"Cannot start interview in status '{interview_session.status}'. Expected 'CREATED'."
        )

    # Server-side interview gating: Candidate must not be NOT_SHORTLISTED
    app_stmt = select(Application).where(Application.id == interview_session.application_id)
    app_obj = await session.scalar(app_stmt)
    if app_obj and (
        app_obj.status == "NOT_SHORTLISTED"
        or app_obj.shortlist_status in ("NOT_SHORTLISTED", "HOLD")
        or (app_obj.shortlist_status == "PENDING" and app_obj.status in ("SCREENING", "RECEIVED", "HOLD", "NOT_SHORTLISTED"))
    ):
        raise CandidateNotShortlistedError("Cannot start interview: Candidate is not shortlisted. Only shortlisted candidates may be interviewed.")

    interview_session.status = "IN_PROGRESS"
    interview_session.started_at = datetime.utcnow()
    interview_session.updated_at = datetime.utcnow()

    # Add initial system message if empty
    if not interview_session.messages:
        sys_msg = InterviewMessage(
            session_id=interview_session.id,
            role="SYSTEM",
            content="Interview session started.",
            sequence_number=1,
        )
        session.add(sys_msg)

    # Initialize / start LangGraph interview workflow if rounds configured
    from app.models.interview_round import InterviewRound
    has_rounds_stmt = (
        select(InterviewRound.id)
        .join(Application, Application.job_id == InterviewRound.job_id)
        .where(Application.id == interview_session.application_id)
        .limit(1)
    )
    has_rounds = (await session.scalar(has_rounds_stmt)) is not None

    if has_rounds:
        try:
            from app.services.interview_graph import start_or_resume_interview_graph
            await start_or_resume_interview_graph(
                session_id=interview_session.id,
                db_session=session,
                organization_id=organization_id,
            )
        except Exception as exc:
            logger.warning(f"Error initializing LangGraph interview workflow: {exc}")

    await session.commit()
    await session.refresh(interview_session)
    return interview_session


async def select_next_interview_capability(
    session: AsyncSession,
    application: Application,
    capabilities: list[Capability],
    asked_question_cap_ids: list[UUID],
) -> Capability:
    ev_stmt = select(Evidence).where(Evidence.application_id == application.id)
    evidence_records = (await session.scalars(ev_stmt)).all()
    ev_map = {ev.capability_id: ev for ev in evidence_records}

    # Priority 1: Capabilities never asked AND (no evidence OR provenance == CLAIM OR strength == INSUFFICIENT)
    p1_candidates = []
    for cap in capabilities:
        if cap.id in asked_question_cap_ids:
            continue
        ev = ev_map.get(cap.id)
        if ev is None or ev.strength == "INSUFFICIENT" or getattr(ev, "provenance", "CLAIM") == "CLAIM":
            p1_candidates.append(cap)
    if p1_candidates:
        return p1_candidates[0]

    # Priority 2: Capabilities never asked with WEAK evidence
    p2_candidates = []
    for cap in capabilities:
        if cap.id in asked_question_cap_ids:
            continue
        ev = ev_map.get(cap.id)
        if ev and ev.strength == "WEAK":
            p2_candidates.append(cap)
    if p2_candidates:
        return p2_candidates[0]

    # Priority 3: Capabilities never asked with MODERATE evidence
    p3_candidates = []
    for cap in capabilities:
        if cap.id in asked_question_cap_ids:
            continue
        ev = ev_map.get(cap.id)
        if ev and ev.strength == "MODERATE":
            p3_candidates.append(cap)
    if p3_candidates:
        return p3_candidates[0]

    # Priority 4: Any unasked capability
    unasked = [c for c in capabilities if c.id not in asked_question_cap_ids]
    if unasked:
        return unasked[0]

    # Fallback: Round-robin least asked capability
    cap_counts = {c.id: asked_question_cap_ids.count(c.id) for c in capabilities}
    sorted_caps = sorted(capabilities, key=lambda c: cap_counts.get(c.id, 0))
    return sorted_caps[0]


async def generate_next_question_for_session(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
) -> InterviewQuestion:
    interview_session = await get_tenant_interview_session(
        session, session_id, organization_id
    )
    if interview_session is None:
        raise InterviewSessionNotFoundError("Interview session not found")

    if interview_session.status != "IN_PROGRESS":
        raise InvalidSessionStateError(
            f"Cannot generate next question for session in '{interview_session.status}' status"
        )

    # Load application and job
    app_stmt = select(Application).where(Application.id == interview_session.application_id)
    application = await session.scalar(app_stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found")

    job_stmt = select(Job).where(Job.id == application.job_id)
    job = await session.scalar(job_stmt)
    if job is None:
        raise ApplicationNotFoundError("Job not found")

    # Load capabilities
    caps_stmt = select(Capability).where(Capability.job_id == application.job_id)
    capabilities = (await session.scalars(caps_stmt)).all()
    if not capabilities:
        raise NoApprovedCapabilitiesError("Job has no capabilities")

    # Load evidence
    ev_stmt = select(Evidence).where(Evidence.application_id == application.id)
    evidence_records = (await session.scalars(ev_stmt)).all()

    # Load verifications
    ver_stmt = select(Verification).where(Verification.application_id == application.id)
    verifications = (await session.scalars(ver_stmt)).all()

    # Previous questions & answers
    asked_questions = interview_session.questions
    asked_cap_ids = [q.capability_id for q in asked_questions]

    # Server selects the target capability
    target_cap = await select_next_interview_capability(
        session, application, list(capabilities), asked_cap_ids
    )

    # Format context for AI
    cap_payloads = [
        {
            "id": str(c.id),
            "name": c.name,
            "description": c.description,
            "importance": c.importance,
        }
        for c in capabilities
    ]

    target_cap_payload = {
        "id": str(target_cap.id),
        "name": target_cap.name,
        "description": target_cap.description,
        "importance": target_cap.importance,
    }

    evidence_payloads = [
        {
            "capability_id": str(e.capability_id),
            "source_type": e.source_type,
            "strength": e.strength,
            "provenance": getattr(e, "provenance", "CLAIM") or "CLAIM",
            "content": e.content,
        }
        for e in evidence_records
    ]

    verification_payloads = [
        {
            "type": v.type,
            "status": v.status,
            "result": v.result,
        }
        for v in verifications
    ]

    history_payloads = [
        {
            "sequence_number": q.sequence_number,
            "capability_id": str(q.capability_id),
            "question": q.question,
            "answer": q.answer,
        }
        for q in asked_questions
    ]

    ai_result = await generate_interview_question(
        job_title=job.title,
        job_description=job.description,
        target_capability=target_cap_payload,
        all_capabilities=cap_payloads,
        evidence_list=evidence_payloads,
        verification_history=verification_payloads,
        interview_history=history_payloads,
    )

    # Server sequence numbers
    next_q_seq = len(asked_questions) + 1

    # Max message sequence number
    max_msg_seq_stmt = select(func.coalesce(func.max(InterviewMessage.sequence_number), 0)).where(
        InterviewMessage.session_id == interview_session.id
    )
    current_max_msg_seq = (await session.scalar(max_msg_seq_stmt)) or 0
    next_msg_seq = current_max_msg_seq + 1

    # Create InterviewQuestion
    new_question = InterviewQuestion(
        session_id=interview_session.id,
        capability_id=target_cap.id,
        question=ai_result.question,
        sequence_number=next_q_seq,
    )
    session.add(new_question)

    # Create AI InterviewMessage
    ai_msg = InterviewMessage(
        session_id=interview_session.id,
        role="AI",
        content=ai_result.question,
        sequence_number=next_msg_seq,
    )
    session.add(ai_msg)

    # Update session current capability
    interview_session.current_capability_id = target_cap.id
    interview_session.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(new_question)
    return new_question


async def submit_interview_answer(
    session: AsyncSession,
    session_id: UUID,
    question_id: UUID,
    answer_text: str,
    organization_id: UUID,
) -> InterviewQuestion:
    interview_session = await get_tenant_interview_session(
        session, session_id, organization_id
    )
    if interview_session is None:
        raise InterviewSessionNotFoundError("Interview session not found")

    if interview_session.status != "IN_PROGRESS":
        raise InvalidSessionStateError(
            f"Cannot answer questions for session in '{interview_session.status}' status"
        )

    q_stmt = select(InterviewQuestion).where(
        InterviewQuestion.id == question_id,
        InterviewQuestion.session_id == interview_session.id,
    )
    question = await session.scalar(q_stmt)
    if question is None:
        raise InterviewQuestionNotFoundError("Interview question not found in this session")

    if question.answer is not None and question.answer.strip():
        raise QuestionAlreadyAnsweredError("This question has already been answered")

    clean_answer = answer_text.strip()
    if not clean_answer:
        raise ValueError("Answer content cannot be empty")

    question.answer = clean_answer
    question.updated_at = datetime.utcnow()

    # Create CANDIDATE InterviewMessage
    max_msg_seq_stmt = select(func.coalesce(func.max(InterviewMessage.sequence_number), 0)).where(
        InterviewMessage.session_id == interview_session.id
    )
    current_max_msg_seq = (await session.scalar(max_msg_seq_stmt)) or 0

    cand_msg = InterviewMessage(
        session_id=interview_session.id,
        role="CANDIDATE",
        content=clean_answer,
        sequence_number=current_max_msg_seq + 1,
    )
    session.add(cand_msg)

    interview_session.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(question)
    return question


async def process_live_candidate_message(
    session: AsyncSession,
    session_id: UUID,
    candidate_text: str,
    organization_id: UUID,
) -> WSAIMessageEvent:
    interview_session = await get_tenant_interview_session(
        session, session_id, organization_id
    )
    if interview_session is None:
        raise InterviewSessionNotFoundError("Interview session not found")

    if interview_session.status != "IN_PROGRESS":
        raise InvalidSessionStateError(
            f"Cannot process messages for session in '{interview_session.status}' status"
        )

    clean_candidate_text = candidate_text.strip()
    if not clean_candidate_text:
        raise ValueError("Candidate message content cannot be empty")

    # Fetch max message sequence number
    max_msg_seq_stmt = select(func.coalesce(func.max(InterviewMessage.sequence_number), 0)).where(
        InterviewMessage.session_id == interview_session.id
    )
    current_max_seq = (await session.scalar(max_msg_seq_stmt)) or 0

    # Persist CANDIDATE message
    cand_msg = InterviewMessage(
        session_id=interview_session.id,
        role="CANDIDATE",
        content=clean_candidate_text,
        sequence_number=current_max_seq + 1,
    )
    session.add(cand_msg)

    # Load context for AI
    app_stmt = select(Application).where(Application.id == interview_session.application_id)
    application = await session.scalar(app_stmt)

    job_stmt = select(Job).where(Job.id == application.job_id)
    job = await session.scalar(job_stmt)

    caps_stmt = select(Capability).where(Capability.job_id == application.job_id)
    capabilities = (await session.scalars(caps_stmt)).all()

    ev_stmt = select(Evidence).where(Evidence.application_id == application.id)
    evidence_records = (await session.scalars(ev_stmt)).all()

    target_cap = None
    if interview_session.current_capability_id:
        target_cap = next((c for c in capabilities if c.id == interview_session.current_capability_id), None)
    if not target_cap and capabilities:
        target_cap = capabilities[0]

    target_cap_payload = (
        {"id": str(target_cap.id), "name": target_cap.name, "description": target_cap.description}
        if target_cap
        else {"name": "General skills"}
    )

    cap_payloads = [{"id": str(c.id), "name": c.name, "description": c.description} for c in capabilities]
    evidence_payloads = [
        {
            "capability_id": str(e.capability_id),
            "source_type": e.source_type,
            "strength": e.strength,
            "provenance": getattr(e, "provenance", "CLAIM") or "CLAIM",
            "content": e.content,
        }
        for e in evidence_records
    ]

    messages_stmt = (
        select(InterviewMessage)
        .where(InterviewMessage.session_id == interview_session.id)
        .order_by(InterviewMessage.sequence_number.asc())
    )
    msg_records = (await session.scalars(messages_stmt)).all()
    msg_payloads = [{"role": m.role, "content": m.content, "sequence_number": m.sequence_number} for m in msg_records]
    # Append the current unsaved candidate message to history payload
    msg_payloads.append({"role": "CANDIDATE", "content": clean_candidate_text, "sequence_number": current_max_seq + 1})

    # Try stateful LangGraph engine if job has configured rounds
    graph_out = None
    has_rounds_stmt = (
        select(InterviewRound.id)
        .where(InterviewRound.job_id == application.job_id)
        .limit(1)
    )
    has_rounds = (await session.scalar(has_rounds_stmt)) is not None

    if has_rounds:
        try:
            from app.services.interview_graph import submit_candidate_answer_to_graph
            graph_res = await submit_candidate_answer_to_graph(
                session_id=interview_session.id,
                answer_text=clean_candidate_text,
                db_session=session,
                organization_id=organization_id,
            )
            if graph_res and graph_res.get("question"):
                graph_out = WSAIMessageEvent(
                    content=graph_res["question"],
                    target_capability=graph_res.get("capability") or (target_cap.name if target_cap else "General"),
                )
            elif graph_res and graph_res.get("is_interview_completed"):
                graph_out = WSAIMessageEvent(
                    content="Thank you for completing the interview. Your responses have been recorded.",
                    target_capability=target_cap.name if target_cap else "General",
                )
        except Exception as exc:
            logger.warning(f"LangGraph execution fallback to standard live AI response: {exc}")

    if graph_out is not None:
        ai_msg = InterviewMessage(
            session_id=interview_session.id,
            role="AI",
            content=graph_out.content,
            sequence_number=current_max_seq + 2,
        )
        session.add(ai_msg)
        interview_session.updated_at = datetime.utcnow()
        await session.commit()
        return graph_out

    ai_response = await generate_live_ai_response(
        job_title=job.title if job else "",
        job_description=job.description if job else "",
        target_capability=target_cap_payload,
        all_capabilities=cap_payloads,
        evidence_list=evidence_payloads,
        messages_history=msg_payloads,
    )

    # Persist AI message
    ai_msg = InterviewMessage(
        session_id=interview_session.id,
        role="AI",
        content=ai_response.content,
        sequence_number=current_max_seq + 2,
    )
    session.add(ai_msg)
    interview_session.updated_at = datetime.utcnow()

    await session.commit()
    return ai_response
