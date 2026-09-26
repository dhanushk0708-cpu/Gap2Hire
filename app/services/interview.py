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
from app.models.interview_answer_analysis import InterviewAnswerAnalysis
from app.models.interview_plan import (
    InterviewPlan,
    InterviewPlanQuestion,
    InterviewPlanRound,
)
from app.models.interview_round import InterviewRound
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.interview import (
    InterviewAnswerAnalysisSchema,
    InterviewAnswerSubmissionResponse,
    NextQuestionPayload,
)
from app.schemas.interview_ws import WSAIMessageEvent
from app.services.ai_interview import (
    analyze_interview_answer,
    generate_interview_question,
    generate_live_ai_response,
    generate_targeted_follow_up,
)
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
            selectinload(InterviewSession.answer_analyses),
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


def compute_interview_rounds_state(
    approved_plan: InterviewPlan | None,
    session_questions: list[InterviewQuestion],
) -> dict:
    if not approved_plan or not approved_plan.rounds:
        return {
            "active_round": None,
            "active_round_number": 1,
            "active_round_title": "General",
            "active_round_status": "COMPLETED" if session_questions else "IN_PROGRESS",
            "is_all_rounds_completed": True if session_questions else False,
            "total_planned_questions": 0,
            "total_rounds": 0,
            "rounds_info": [],
        }

    rounds_sorted = sorted(approved_plan.rounds, key=lambda r: (r.sequence, r.round_number))
    rounds_info = []
    active_round = None
    is_all_done = True
    total_planned = sum(len(r.questions) for r in rounds_sorted)

    asked_dict = {q.plan_question_id: q for q in session_questions if q.plan_question_id is not None}
    asked_texts_dict = {q.question.strip().lower(): q for q in session_questions}

    for r in rounds_sorted:
        answered_count = 0
        for pq in r.questions:
            matching_q = asked_dict.get(pq.id) or asked_texts_dict.get(pq.question_text.strip().lower())
            if matching_q and matching_q.answer and matching_q.answer.strip():
                answered_count += 1

        is_r_done = (len(r.questions) > 0 and answered_count >= len(r.questions))
        if not is_r_done and active_round is None:
            active_round = r
            is_all_done = False

        status_str = "COMPLETED" if is_r_done else ("IN_PROGRESS" if active_round == r else "PENDING")
        rounds_info.append({
            "round_id": str(r.id),
            "round_number": r.round_number,
            "title": r.title,
            "objective": r.objective,
            "status": status_str,
            "total_questions": len(r.questions),
            "questions_completed": answered_count,
        })

    if active_round is None and rounds_sorted:
        active_round = rounds_sorted[-1]
        active_status = "COMPLETED"
    else:
        active_status = "IN_PROGRESS"

    return {
        "active_round": active_round,
        "active_round_number": active_round.round_number if active_round else 1,
        "active_round_title": active_round.title if active_round else "General",
        "active_round_status": active_status,
        "is_all_rounds_completed": is_all_done,
        "total_planned_questions": total_planned,
        "total_rounds": len(rounds_sorted),
        "rounds_info": rounds_info,
    }


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

    # Previous questions
    asked_questions = interview_session.questions
    asked_plan_ids = {q.plan_question_id for q in asked_questions if q.plan_question_id is not None}
    asked_texts = {q.question.strip().lower() for q in asked_questions}

    # Next sequence numbers
    next_q_seq = len(asked_questions) + 1
    max_msg_seq_stmt = select(func.coalesce(func.max(InterviewMessage.sequence_number), 0)).where(
        InterviewMessage.session_id == interview_session.id
    )
    current_max_msg_seq = (await session.scalar(max_msg_seq_stmt)) or 0
    next_msg_seq = current_max_msg_seq + 1

    # Check for approved interview plan first
    plan_stmt = (
        select(InterviewPlan)
        .where(
            InterviewPlan.application_id == application.id,
            InterviewPlan.organization_id == organization_id,
            InterviewPlan.status == "APPROVED",
        )
        .options(
            selectinload(InterviewPlan.rounds)
            .selectinload(InterviewPlanRound.questions),
        )
        .order_by(InterviewPlan.version.desc())
    )
    approved_plan = await session.scalar(plan_stmt)

    if approved_plan and approved_plan.rounds:
        round_state = compute_interview_rounds_state(approved_plan, asked_questions)
        active_round = round_state["active_round"]

        if active_round and round_state["active_round_status"] == "IN_PROGRESS":
            next_plan_q = next(
                (pq for pq in active_round.questions if pq.id not in asked_plan_ids and pq.question_text.strip().lower() not in asked_texts),
                None,
            )
            if next_plan_q is not None:
                matched_cap = next(
                    (c for c in capabilities if c.name.lower() == next_plan_q.concept.lower()),
                    capabilities[0] if capabilities else None,
                )

                # If starting a new round, persist system transition event
                if interview_session.current_round_id != active_round.id:
                    interview_session.current_round_id = active_round.id
                    sys_msg = InterviewMessage(
                        session_id=interview_session.id,
                        role="SYSTEM",
                        content=f"Round {active_round.round_number}: {active_round.title} started.",
                        sequence_number=next_msg_seq,
                    )
                    session.add(sys_msg)
                    next_msg_seq += 1

                new_question = InterviewQuestion(
                    session_id=interview_session.id,
                    capability_id=matched_cap.id if matched_cap else None,
                    plan_question_id=next_plan_q.id,
                    parent_question_id=None,
                    question_type="PLANNED",
                    concept=next_plan_q.concept,
                    question=next_plan_q.question_text,
                    sequence_number=next_q_seq,
                )
                session.add(new_question)

                ai_msg = InterviewMessage(
                    session_id=interview_session.id,
                    role="AI",
                    content=next_plan_q.question_text,
                    sequence_number=next_msg_seq,
                )
                session.add(ai_msg)

                if matched_cap:
                    interview_session.current_capability_id = matched_cap.id
                interview_session.updated_at = datetime.utcnow()

                await session.commit()
                await session.refresh(new_question)
                return new_question

    if not capabilities:
        raise NoApprovedCapabilitiesError("Job has no capabilities")

    # Dynamic capability fallback if no approved plan or plan questions exhausted
    ev_stmt = select(Evidence).where(Evidence.application_id == application.id)
    evidence_records = (await session.scalars(ev_stmt)).all()

    ver_stmt = select(Verification).where(Verification.application_id == application.id)
    verifications = (await session.scalars(ver_stmt)).all()

    asked_cap_ids = [q.capability_id for q in asked_questions if q.capability_id is not None]
    target_cap = await select_next_interview_capability(
        session, application, list(capabilities), asked_cap_ids
    )

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
        {"type": v.type, "status": v.status, "result": v.result}
        for v in verifications
    ]
    history_payloads = [
        {
            "sequence_number": q.sequence_number,
            "capability_id": str(q.capability_id) if q.capability_id else None,
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

    new_question = InterviewQuestion(
        session_id=interview_session.id,
        capability_id=target_cap.id,
        plan_question_id=None,
        parent_question_id=None,
        question_type="PLANNED",
        concept=target_cap.name,
        question=ai_result.question,
        sequence_number=next_q_seq,
    )
    session.add(new_question)

    ai_msg = InterviewMessage(
        session_id=interview_session.id,
        role="AI",
        content=ai_result.question,
        sequence_number=next_msg_seq,
    )
    session.add(ai_msg)

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
) -> InterviewAnswerSubmissionResponse:
    interview_session = await get_tenant_interview_session(
        session, session_id, organization_id
    )
    if interview_session is None:
        raise InterviewSessionNotFoundError("Interview session not found")

    if interview_session.status != "IN_PROGRESS":
        raise InvalidSessionStateError(
            f"Cannot answer questions for session in '{interview_session.status}' status"
        )

    q_stmt = (
        select(InterviewQuestion)
        .where(
            InterviewQuestion.id == question_id,
            InterviewQuestion.session_id == interview_session.id,
        )
        .options(selectinload(InterviewQuestion.capability))
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
    current_max_msg_seq += 1

    # Analyze answer with AI
    concept_name = question.concept or (question.capability.name if question.capability else "Technical Competence")
    analysis_data = await analyze_interview_answer(
        question_text=question.question,
        concept=concept_name,
        candidate_answer=clean_answer,
    )

    # Persist structured analysis
    analysis_record = InterviewAnswerAnalysis(
        session_id=interview_session.id,
        question_id=question.id,
        analysis=analysis_data,
    )
    session.add(analysis_record)

    # Load all existing questions in session for duplicate prevention
    all_qs_stmt = select(InterviewQuestion).where(InterviewQuestion.session_id == interview_session.id)
    all_asked = list((await session.scalars(all_qs_stmt)).all())
    asked_plan_ids = {q.plan_question_id for q in all_asked if q.plan_question_id is not None}
    asked_texts = {q.question.strip().lower() for q in all_asked}

    # Check for approved interview plan
    plan_stmt = (
        select(InterviewPlan)
        .where(
            InterviewPlan.application_id == interview_session.application_id,
            InterviewPlan.organization_id == organization_id,
            InterviewPlan.status == "APPROVED",
        )
        .options(
            selectinload(InterviewPlan.rounds)
            .selectinload(InterviewPlanRound.questions),
        )
        .order_by(InterviewPlan.version.desc())
    )
    approved_plan = await session.scalar(plan_stmt)

    is_sufficient = analysis_data.get("answer_quality") == "SUFFICIENT"
    follow_up_needed = analysis_data.get("follow_up_needed", not is_sufficient)

    next_q_obj: InterviewQuestion | None = None
    action: str = "NEXT_QUESTION"

    # Identify current round of the answered question
    rounds_sorted = sorted(approved_plan.rounds, key=lambda r: (r.sequence, r.round_number)) if approved_plan and approved_plan.rounds else []
    current_round = None

    if rounds_sorted:
        if question.plan_question_id:
            current_round = next((r for r in rounds_sorted if any(pq.id == question.plan_question_id for pq in r.questions)), None)
        if not current_round and question.parent_question_id:
            parent_q = next((q_item for q_item in all_asked if q_item.id == question.parent_question_id), None)
            if parent_q and parent_q.plan_question_id:
                current_round = next((r for r in rounds_sorted if any(pq.id == parent_q.plan_question_id for pq in r.questions)), None)
        if not current_round:
            current_round = rounds_sorted[0]

    current_round_number = current_round.round_number if current_round else 1
    current_round_title = current_round.title if current_round else "General"
    round_status = "IN_PROGRESS"
    interview_status = "IN_PROGRESS"

    if follow_up_needed or not is_sufficient:
        # Generate targeted follow-up question -> MUST remain inside current round
        missing_pts = analysis_data.get("missing_points", [])
        fu_reason = analysis_data.get("follow_up_reason", "")
        follow_up_text = await generate_targeted_follow_up(
            question_text=question.question,
            concept=concept_name,
            candidate_answer=clean_answer,
            missing_points=missing_pts,
            follow_up_reason=fu_reason,
            existing_questions=list(asked_texts),
        )

        # Duplicate check / fallback uniqueness
        if follow_up_text.strip().lower() in asked_texts:
            follow_up_text = f"Can you detail your practical experience with {concept_name} addressing: {', '.join(missing_pts) if missing_pts else fu_reason}?"

        next_q_seq = len(all_asked) + 1
        next_q_obj = InterviewQuestion(
            session_id=interview_session.id,
            capability_id=question.capability_id,
            plan_question_id=None,
            parent_question_id=question.id,
            question_type="FOLLOW_UP",
            concept=concept_name,
            question=follow_up_text,
            sequence_number=next_q_seq,
        )
        session.add(next_q_obj)

        ai_msg = InterviewMessage(
            session_id=interview_session.id,
            role="AI",
            content=follow_up_text,
            sequence_number=current_max_msg_seq + 1,
        )
        session.add(ai_msg)
        action = "FOLLOW_UP"

    else:
        # SUFFICIENT -> Check if current round has more unasked planned questions
        next_plan_q = None
        if current_round:
            next_plan_q = next(
                (pq for pq in current_round.questions if pq.id not in asked_plan_ids and pq.question_text.strip().lower() not in asked_texts),
                None,
            )

        if next_plan_q is not None:
            # More questions in CURRENT round
            next_q_seq = len(all_asked) + 1
            next_q_obj = InterviewQuestion(
                session_id=interview_session.id,
                capability_id=question.capability_id,
                plan_question_id=next_plan_q.id,
                parent_question_id=None,
                question_type="PLANNED",
                concept=next_plan_q.concept,
                question=next_plan_q.question_text,
                sequence_number=next_q_seq,
            )
            session.add(next_q_obj)

            ai_msg = InterviewMessage(
                session_id=interview_session.id,
                role="AI",
                content=next_plan_q.question_text,
                sequence_number=current_max_msg_seq + 1,
            )
            session.add(ai_msg)
            action = "NEXT_QUESTION"

        else:
            # CURRENT ROUND COMPLETED -> Determine if next round exists
            if current_round:
                round_complete_msg = InterviewMessage(
                    session_id=interview_session.id,
                    role="SYSTEM",
                    content=f"Round {current_round.round_number}: {current_round.title} completed.",
                    sequence_number=current_max_msg_seq + 1,
                )
                session.add(round_complete_msg)
                current_max_msg_seq += 1

            # Find next round in sequence
            next_round = None
            if current_round and rounds_sorted:
                next_round = next(
                    (r for r in rounds_sorted if r.sequence > current_round.sequence or (r.sequence == current_round.sequence and r.round_number > current_round.round_number)),
                    None,
                )

            if next_round is not None:
                # Transition to next round
                round_start_msg = InterviewMessage(
                    session_id=interview_session.id,
                    role="SYSTEM",
                    content=f"Round {next_round.round_number}: {next_round.title} started.",
                    sequence_number=current_max_msg_seq + 1,
                )
                session.add(round_start_msg)
                current_max_msg_seq += 1

                current_round_number = next_round.round_number
                current_round_title = next_round.title

                # Load first planned question in next round
                pq_next = next_round.questions[0] if next_round.questions else None
                if pq_next is not None:
                    next_q_seq = len(all_asked) + 1
                    next_q_obj = InterviewQuestion(
                        session_id=interview_session.id,
                        capability_id=question.capability_id,
                        plan_question_id=pq_next.id,
                        parent_question_id=None,
                        question_type="PLANNED",
                        concept=pq_next.concept,
                        question=pq_next.question_text,
                        sequence_number=next_q_seq,
                    )
                    session.add(next_q_obj)

                    ai_msg = InterviewMessage(
                        session_id=interview_session.id,
                        role="AI",
                        content=pq_next.question_text,
                        sequence_number=current_max_msg_seq + 1,
                    )
                    session.add(ai_msg)
                    action = "NEXT_QUESTION"
                else:
                    action = "ROUND_COMPLETE"
                    next_q_obj = None

            else:
                # All rounds finished -> Complete interview session
                action = "ROUND_COMPLETE"
                round_status = "COMPLETED"
                interview_status = "COMPLETED"
                interview_session.status = "COMPLETED"
                interview_session.ended_at = datetime.utcnow()
                complete_msg = InterviewMessage(
                    session_id=interview_session.id,
                    role="SYSTEM",
                    content="Interview session completed. All rounds finished.",
                    sequence_number=current_max_msg_seq + 1,
                )
                session.add(complete_msg)
                next_q_obj = None

    interview_session.updated_at = datetime.utcnow()
    await session.commit()

    if next_q_obj is not None:
        await session.refresh(next_q_obj)

    next_q_payload: NextQuestionPayload | None = None
    if next_q_obj is not None:
        next_q_payload = NextQuestionPayload(
            id=next_q_obj.id,
            question=next_q_obj.question,
            concept=next_q_obj.concept,
            question_type=next_q_obj.question_type,
            sequence_number=next_q_obj.sequence_number,
            plan_question_id=next_q_obj.plan_question_id,
            parent_question_id=next_q_obj.parent_question_id,
            round_number=current_round_number,
            round_title=current_round_title,
        )

    return InterviewAnswerSubmissionResponse(
        analysis=InterviewAnswerAnalysisSchema(
            answer_quality=analysis_data["answer_quality"],
            evidence_state=analysis_data["evidence_state"],
            key_findings=analysis_data.get("key_findings", []),
            missing_points=analysis_data.get("missing_points", []),
            follow_up_needed=analysis_data.get("follow_up_needed", False),
            follow_up_reason=analysis_data.get("follow_up_reason", ""),
        ),
        action=action,
        next_question=next_q_payload,
        question_id=question.id,
        answer=clean_answer,
        round_number=current_round_number,
        round_title=current_round_title,
        round_status=round_status,
        interview_status=interview_status,
    )


async def get_interview_execution_state(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
) -> dict:
    interview_session = await get_tenant_interview_session(
        session, session_id, organization_id
    )
    if interview_session is None:
        raise InterviewSessionNotFoundError("Interview session not found")

    # Load approved plan
    plan_stmt = (
        select(InterviewPlan)
        .where(
            InterviewPlan.application_id == interview_session.application_id,
            InterviewPlan.organization_id == organization_id,
            InterviewPlan.status == "APPROVED",
        )
        .options(
            selectinload(InterviewPlan.rounds)
            .selectinload(InterviewPlanRound.questions),
        )
        .order_by(InterviewPlan.version.desc())
    )
    approved_plan = await session.scalar(plan_stmt)

    # Questions & metrics
    all_qs = list(interview_session.questions)
    completed_count = sum(1 for q in all_qs if q.answer is not None and q.answer.strip())
    follow_up_count = sum(1 for q in all_qs if q.question_type == "FOLLOW_UP" or q.parent_question_id is not None)

    latest_q = all_qs[-1] if all_qs else None
    latest_q_text = latest_q.question if latest_q else None
    latest_q_type = latest_q.question_type if latest_q else None

    round_state = compute_interview_rounds_state(approved_plan, all_qs)
    active_round = round_state["active_round"]

    current_round_dict = {
        "round_number": round_state["active_round_number"],
        "title": round_state["active_round_title"],
        "objective": active_round.objective if active_round else "",
        "round_id": str(active_round.id) if active_round else None,
    } if active_round else None

    return {
        "session_id": str(interview_session.id),
        "interview_status": interview_session.status,
        "current_round": current_round_dict,
        "current_question": latest_q_text,
        "current_question_type": latest_q_type,
        "round_status": round_state["active_round_status"],
        "questions_completed": completed_count,
        "total_planned_questions": round_state["total_planned_questions"],
        "follow_up_count": follow_up_count,
        "total_rounds": round_state["total_rounds"],
        "rounds": round_state["rounds_info"],
    }


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
