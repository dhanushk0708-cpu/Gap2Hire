from datetime import datetime
import json
import logging
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.application import Application
from app.models.interview_dataset import (
    InterviewDatasetFile,
    InterviewDatasetQuestion,
    InterviewQuestionDataset,
)
from app.models.interview_plan import (
    InterviewPlan,
    InterviewPlanQuestion,
    InterviewPlanRound,
)
from app.models.job import Job
from app.schemas.interview_plan import (
    InterviewPlanApprovalRequest,
    InterviewPlanQuestionSchema,
    InterviewPlanResponse,
    InterviewPlanRoundSchema,
    InterviewPlanUpdateRequest,
    RoundQuestionGeneratePreviewRequest,
)
from app.services.application import ApplicationNotFoundError
from app.services.interview_pre_analysis import build_candidate_interview_pre_analysis

logger = logging.getLogger(__name__)


class InterviewPlanNotFoundError(Exception):
    """Raised when an interview plan is not found or inaccessible."""
    pass


class InvalidPlanStateError(Exception):
    """Raised when attempting an illegal operation on an interview plan."""
    pass


class ConcurrentUpdateError(Exception):
    """Raised when an optimistic concurrency conflict is detected."""
    pass


async def generate_candidate_interview_plan(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    dataset_file_id: UUID | None = None,
    created_by: UUID | None = None,
) -> InterviewPlan:
    """
    Generates a candidate-specific interview plan grounded in the candidate's pre-interview analysis:
    - Selects concepts based on candidate claims, demonstrated skills, and unknowns.
    - Selects relevant questions from the uploaded question datasets or synthesizes grounded questions.
    - Configures structured round criteria, expected evidence, and question generation mode.
    - Versions the plan (e.g. v1, v2) and marks older drafts as SUPERSEDED.
    """
    # 1. Tenant application & job verification
    app_stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
        .options(selectinload(Application.job))
    )
    application = await session.scalar(app_stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found or inaccessible.")

    job = application.job

    # 2. Build candidate pre-interview analysis
    pre_analysis = await build_candidate_interview_pre_analysis(
        session=session,
        application_id=application_id,
        organization_id=organization_id,
    )

    # 3. Resolve interview dataset file
    if dataset_file_id:
        file_stmt = select(InterviewDatasetFile).where(
            InterviewDatasetFile.id == dataset_file_id,
            InterviewDatasetFile.organization_id == organization_id,
        )
        dataset_file = await session.scalar(file_stmt)
    else:
        file_stmt = (
            select(InterviewDatasetFile)
            .where(
                InterviewDatasetFile.organization_id == organization_id,
                (InterviewDatasetFile.job_id == job.id) | (InterviewDatasetFile.job_id.is_(None)),
            )
            .order_by(InterviewDatasetFile.created_at.desc())
        )
        dataset_file = await session.scalar(file_stmt)

    # Load available questions grouped by concept
    questions_by_concept: dict[str, list[InterviewDatasetQuestion]] = {}
    if dataset_file:
        q_stmt = (
            select(InterviewDatasetQuestion)
            .join(InterviewQuestionDataset, InterviewQuestionDataset.id == InterviewDatasetQuestion.dataset_id)
            .where(InterviewQuestionDataset.file_id == dataset_file.id)
            .order_by(InterviewDatasetQuestion.created_at.asc())
        )
        all_ds_questions = list((await session.scalars(q_stmt)).all())
        for q in all_ds_questions:
            norm_c = q.concept.strip().lower()
            questions_by_concept.setdefault(norm_c, []).append(q)

    # Determine version number
    version_stmt = select(func.max(InterviewPlan.version)).where(
        InterviewPlan.application_id == application_id
    )
    max_ver = await session.scalar(version_stmt) or 0
    new_version = max_ver + 1

    # Supersede any existing DRAFT plans for this application
    existing_drafts_stmt = select(InterviewPlan).where(
        InterviewPlan.application_id == application_id,
        InterviewPlan.status == "DRAFT",
    )
    existing_drafts = list((await session.scalars(existing_drafts_stmt)).all())
    for d in existing_drafts:
        d.status = "SUPERSEDED"

    # Summaries
    strengths_summary = "; ".join([f"{s['capability_name']} ({s['provenance']})" for s in pre_analysis.candidate_strengths]) or "None verified"
    targets_summary = "; ".join([f"{t['capability_name']} ({t['current_state']})" for t in pre_analysis.verification_targets]) or "All requirements met"

    plan = InterviewPlan(
        id=uuid4(),
        organization_id=organization_id,
        application_id=application_id,
        job_id=job.id,
        dataset_file_id=dataset_file.id if dataset_file else None,
        version=new_version,
        lock_version=1,
        status="DRAFT",
        candidate_strengths_summary=strengths_summary,
        verification_targets_summary=targets_summary,
        created_by=created_by,
    )
    session.add(plan)

    used_question_ids: set[UUID] = set()
    used_question_texts: set[str] = set()

    claims_concepts = [c["capability_name"] for c in pre_analysis.candidate_claims]
    demonstrated_concepts = [s["capability_name"] for s in pre_analysis.candidate_strengths]
    unknown_concepts = [u["capability_name"] for u in pre_analysis.candidate_unknowns]

    # ROUND 1: Core Fundamentals & Primary Claims
    round1_concepts = _select_round_concepts(
        primary_list=claims_concepts + demonstrated_concepts,
        fallback_list=pre_analysis.relevant_concepts,
        max_concepts=3,
    )
    round1 = InterviewPlanRound(
        id=uuid4(),
        plan_id=plan.id,
        round_number=1,
        title="Round 1 — Core Fundamentals & Preliminary Claims",
        objective="Evaluate core engineering fundamentals and verify preliminary technical resume claims.",
        description="Foundational assessment testing practical syntax, concepts, and primary resume assertions.",
        concepts=round1_concepts,
        evaluation_criteria=[
            "Direct understanding of core architectural patterns and standard library usage.",
            "Accurate differentiation between conceptual definitions and production implementation.",
            "Clear technical communication of claimed resume capabilities.",
        ],
        expected_evidence=[
            "Practical code examples or architectural walkthroughs from recent projects.",
            "Precise identification of common performance pitfalls or memory considerations.",
        ],
        question_generation_mode="AI_GENERATED",
        difficulty="MEDIUM",
        estimated_duration_minutes=30,
        required=True,
        reasoning=(
            f"Targets preliminary claims: {', '.join(claims_concepts) if claims_concepts else 'general capabilities'}. "
            "Validates candidate's self-reported understanding against standard job requirements."
        ),
        sequence=1,
    )
    session.add(round1)
    _populate_round_questions(
        session=session,
        round_id=round1.id,
        concepts=round1_concepts,
        questions_by_concept=questions_by_concept,
        used_question_ids=used_question_ids,
        used_question_texts=used_question_texts,
        pre_analysis=pre_analysis,
        target_question_count=3,
        round_difficulty="MEDIUM",
    )

    # ROUND 2: Applied Engineering & Gap Probing
    round2_concepts = _select_round_concepts(
        primary_list=unknown_concepts + [c for c in claims_concepts if c not in round1_concepts],
        fallback_list=pre_analysis.relevant_concepts,
        max_concepts=3,
    )
    round2 = InterviewPlanRound(
        id=uuid4(),
        plan_id=plan.id,
        round_number=2,
        title="Round 2 — Applied Engineering & Gap Exploration",
        objective="Probe unverified capabilities, architecture patterns, and technical problem-solving depth.",
        description="Focused deep-dive targeting unverified competencies and edge cases.",
        concepts=round2_concepts,
        evaluation_criteria=[
            "Depth of technical reasoning under novel or constrained scenarios.",
            "Ability to explain trade-offs between speed, maintainability, and scalability.",
            "Rigorous troubleshooting approach to unverified system areas.",
        ],
        expected_evidence=[
            "Detailed explanation of concurrency, caching, or transaction boundaries.",
            "Demonstration of defensive programming and failure recovery strategies.",
        ],
        question_generation_mode="AI_GENERATED",
        difficulty="HARD",
        estimated_duration_minutes=35,
        required=True,
        reasoning=(
            f"Targets uncorroborated capabilities: {', '.join(unknown_concepts) if unknown_concepts else 'advanced domain requirements'}. "
            "Identifies depth of knowledge where resume evidence was missing or insufficient."
        ),
        sequence=2,
    )
    session.add(round2)
    _populate_round_questions(
        session=session,
        round_id=round2.id,
        concepts=round2_concepts,
        questions_by_concept=questions_by_concept,
        used_question_ids=used_question_ids,
        used_question_texts=used_question_texts,
        pre_analysis=pre_analysis,
        target_question_count=3,
        round_difficulty="HARD",
    )

    # ROUND 3: Practical Verification & System Design
    round3_concepts = pre_analysis.relevant_concepts[:3] if pre_analysis.relevant_concepts else ["Architecture", "System Design"]
    round3 = InterviewPlanRound(
        id=uuid4(),
        plan_id=plan.id,
        round_number=3,
        title="Round 3 — Practical Architecture & Production Decisions",
        objective="Examine candidate's real project architecture, design trade-offs, and production troubleshooting decisions.",
        description="End-to-end design review evaluating system architecture and reliability trade-offs.",
        concepts=round3_concepts,
        evaluation_criteria=[
            "Holistic system design encompassing data pipelines, observability, and SLA management.",
            "Pragmatic balancing of engineering perfection vs business deadlines.",
        ],
        expected_evidence=[
            "Concrete post-mortem or production outage resolution example.",
            "Clear justification for database, queue, or API paradigm choices.",
        ],
        question_generation_mode="AI_GENERATED",
        difficulty="HARD",
        estimated_duration_minutes=35,
        required=True,
        reasoning="Examines practical engineering execution, real project experience, and architectural decision-making.",
        sequence=3,
    )
    session.add(round3)
    _populate_round_questions(
        session=session,
        round_id=round3.id,
        concepts=round3_concepts,
        questions_by_concept=questions_by_concept,
        used_question_ids=used_question_ids,
        used_question_texts=used_question_texts,
        pre_analysis=pre_analysis,
        target_question_count=2,
        round_difficulty="HARD",
    )

    await session.commit()
    return await get_interview_plan(session, organization_id, plan.id)


def _select_round_concepts(
    primary_list: list[str],
    fallback_list: list[str],
    max_concepts: int = 3,
) -> list[str]:
    selected: list[str] = []
    for c in primary_list:
        if c not in selected:
            selected.append(c)
        if len(selected) >= max_concepts:
            return selected

    for f in fallback_list:
        if f not in selected:
            selected.append(f)
        if len(selected) >= max_concepts:
            return selected

    return selected if selected else ["Engineering"]


def _populate_round_questions(
    session: AsyncSession,
    round_id: UUID,
    concepts: list[str],
    questions_by_concept: dict[str, list[InterviewDatasetQuestion]],
    used_question_ids: set[UUID],
    used_question_texts: set[str],
    pre_analysis: Any,
    target_question_count: int = 3,
    round_difficulty: str = "MEDIUM",
):
    seq = 1

    claims_set = {c["capability_name"].lower() for c in pre_analysis.candidate_claims}
    unknown_set = {u["capability_name"].lower() for u in pre_analysis.candidate_unknowns}
    demonstrated_set = {s["capability_name"].lower() for s in pre_analysis.candidate_strengths}

    for concept in concepts:
        c_lower = concept.lower()
        pool = questions_by_concept.get(c_lower, [])
        if not pool:
            pool = [q for k, qs in questions_by_concept.items() if c_lower in k for q in qs]

        for q in pool:
            if q.id in used_question_ids or q.question_text.lower() in used_question_texts:
                continue

            if c_lower in claims_set:
                purpose = f"Verify {concept} depth and practical experience (currently resume CLAIM)"
                ev_ver = f"{concept} (CLAIM)"
            elif c_lower in unknown_set:
                purpose = f"Probe unknown capability {concept} to determine foundational competency"
                ev_ver = f"{concept} (UNKNOWN)"
            elif c_lower in demonstrated_set:
                purpose = f"Assess advanced knowledge in demonstrated capability {concept}"
                ev_ver = f"{concept} (DEMONSTRATED)"
            else:
                purpose = f"Assess competency in {concept}"
                ev_ver = f"{concept}"

            plan_q = InterviewPlanQuestion(
                id=uuid4(),
                round_id=round_id,
                dataset_question_id=q.id,
                question_text=q.question_text,
                concept=concept,
                difficulty=q.difficulty or round_difficulty,
                question_type=q.question_type or "CONCEPTUAL",
                purpose=purpose,
                evidence_being_verified=ev_ver,
                is_hr_authored=False,
                status="APPROVED",
                sequence=seq,
            )
            session.add(plan_q)
            used_question_ids.add(q.id)
            used_question_texts.add(q.question_text.lower())
            seq += 1

            if seq > target_question_count:
                break

        if seq > target_question_count:
            break

    # If dataset had fewer questions than target_question_count, generate grounded questions
    if seq <= target_question_count:
        for concept in concepts:
            c_lower = concept.lower()
            synth_text = f"Explain the architectural patterns, trade-offs, and practical design decisions you employ with {concept} in high-reliability applications."
            if synth_text.lower() in used_question_texts:
                continue

            if c_lower in claims_set:
                purpose = f"Verify candidate claim for {concept} with practical architectural questions"
                ev_ver = f"{concept} (CLAIM)"
            elif c_lower in unknown_set:
                purpose = f"Probe foundational understanding of {concept}"
                ev_ver = f"{concept} (UNKNOWN)"
            else:
                purpose = f"Evaluate depth of competency in {concept}"
                ev_ver = f"{concept}"

            plan_q = InterviewPlanQuestion(
                id=uuid4(),
                round_id=round_id,
                dataset_question_id=None,
                question_text=synth_text,
                concept=concept,
                difficulty=round_difficulty,
                question_type="SYSTEM_DESIGN",
                purpose=purpose,
                evidence_being_verified=ev_ver,
                is_hr_authored=False,
                status="APPROVED",
                sequence=seq,
            )
            session.add(plan_q)
            used_question_texts.add(synth_text.lower())
            seq += 1
            if seq > target_question_count:
                break


async def get_interview_plan(
    session: AsyncSession,
    organization_id: UUID,
    plan_id: UUID,
) -> InterviewPlan:
    """Fetches an interview plan with all its rounds and questions under tenant isolation."""
    stmt = (
        select(InterviewPlan)
        .where(
            InterviewPlan.id == plan_id,
            InterviewPlan.organization_id == organization_id,
        )
        .options(
            selectinload(InterviewPlan.rounds).selectinload(InterviewPlanRound.questions),
            selectinload(InterviewPlan.application).selectinload(Application.candidate),
            selectinload(InterviewPlan.job),
        )
    )
    plan = await session.scalar(stmt)
    if not plan:
        raise InterviewPlanNotFoundError("Interview plan not found or inaccessible.")
    return plan


async def list_candidate_interview_plans(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> list[InterviewPlan]:
    """Lists all historical and current interview plans for a candidate application."""
    stmt = (
        select(InterviewPlan)
        .where(
            InterviewPlan.application_id == application_id,
            InterviewPlan.organization_id == organization_id,
        )
        .options(
            selectinload(InterviewPlan.rounds).selectinload(InterviewPlanRound.questions)
        )
        .order_by(InterviewPlan.version.desc())
    )
    return list((await session.scalars(stmt)).all())


async def approve_interview_plan(
    session: AsyncSession,
    organization_id: UUID,
    plan_id: UUID,
    approved_by: UUID,
    notes: str | None = None,
) -> InterviewPlan:
    """
    Approves an interview plan:
    - Verifies plan is in DRAFT state.
    - Marks status = APPROVED and records timestamp and approver.
    - Preserves approved version immutably.
    """
    plan = await get_interview_plan(session, organization_id, plan_id)

    if plan.status == "APPROVED":
        return plan

    if plan.status in {"SUPERSEDED", "REJECTED"}:
        raise InvalidPlanStateError(f"Cannot approve an interview plan with status '{plan.status}'.")

    plan.status = "APPROVED"
    plan.approved_by = approved_by
    plan.approved_at = datetime.utcnow()
    if notes:
        plan.hr_feedback = notes

    await session.commit()
    await session.refresh(plan)
    return plan


async def update_interview_plan(
    session: AsyncSession,
    organization_id: UUID,
    plan_id: UUID,
    data: InterviewPlanUpdateRequest,
    updated_by: UUID | None = None,
) -> InterviewPlan:
    """
    Allows HR user to edit rounds, objectives, durations, criteria, and questions.
    - Checks lock_version for optimistic concurrency conflict prevention.
    - If plan is in DRAFT state: updates in place and increments lock_version.
    - If plan is in APPROVED state: creates a new DRAFT plan version (version + 1),
      preserving the original approved version immutably for existing scheduled/completed interviews.
    """
    plan = await get_interview_plan(session, organization_id, plan_id)

    # Optimistic concurrency check
    if data.lock_version is not None and plan.lock_version != data.lock_version:
        raise ConcurrentUpdateError(
            f"Conflict: The interview plan has been modified by another session (expected lock_version {plan.lock_version}, got {data.lock_version}). Please refresh and try again."
        )

    if plan.status == "APPROVED":
        # Fork a new version to preserve the approved plan version immutably
        version_stmt = select(func.max(InterviewPlan.version)).where(
            InterviewPlan.application_id == plan.application_id
        )
        max_ver = await session.scalar(version_stmt) or plan.version
        new_version = max_ver + 1

        new_plan = InterviewPlan(
            id=uuid4(),
            organization_id=organization_id,
            application_id=plan.application_id,
            job_id=plan.job_id,
            dataset_file_id=plan.dataset_file_id,
            version=new_version,
            lock_version=1,
            status="DRAFT",
            candidate_strengths_summary=plan.candidate_strengths_summary,
            verification_targets_summary=plan.verification_targets_summary,
            hr_feedback=data.hr_feedback if data.hr_feedback is not None else plan.hr_feedback,
            created_by=updated_by or plan.created_by,
        )
        session.add(new_plan)
        target_plan = new_plan
    else:
        # Update draft in place
        if data.hr_feedback is not None:
            plan.hr_feedback = data.hr_feedback
        plan.lock_version += 1
        plan.rounds.clear()
        await session.flush()
        target_plan = plan

    # Re-populate rounds & questions
    for r_idx, r_data in enumerate(data.rounds, start=1):
        round_obj = InterviewPlanRound(
            id=uuid4(),
            plan_id=target_plan.id,
            round_number=r_data.round_number or r_idx,
            title=r_data.title,
            objective=r_data.objective,
            description=r_data.description,
            concepts=r_data.concepts,
            evaluation_criteria=r_data.evaluation_criteria,
            expected_evidence=r_data.expected_evidence,
            question_generation_mode=r_data.question_generation_mode or "AI_GENERATED",
            difficulty=r_data.difficulty or "MEDIUM",
            estimated_duration_minutes=r_data.estimated_duration_minutes,
            required=r_data.required,
            reasoning=r_data.reasoning,
            sequence=r_idx,
        )
        target_plan.rounds.append(round_obj)

        for q_idx, q_data in enumerate(r_data.questions, start=1):
            q_obj = InterviewPlanQuestion(
                id=uuid4(),
                round_id=round_obj.id,
                dataset_question_id=q_data.dataset_question_id,
                question_text=q_data.question_text,
                concept=q_data.concept,
                difficulty=q_data.difficulty,
                question_type=q_data.question_type,
                purpose=q_data.purpose,
                evidence_being_verified=q_data.evidence_being_verified,
                is_hr_authored=q_data.is_hr_authored,
                status=q_data.status or "APPROVED",
                sequence=q_idx,
            )
            round_obj.questions.append(q_obj)

    target_plan.updated_at = datetime.utcnow()
    await session.commit()
    return await get_interview_plan(session, organization_id, target_plan.id)


async def preview_or_generate_round_questions(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    request: RoundQuestionGeneratePreviewRequest,
) -> list[InterviewPlanQuestionSchema]:
    """
    Generates previewable question proposals for a round based on:
    - Mode: AI_GENERATED (all generated), HR_DEFINED (only HR questions), HYBRID (preserve HR + generate remaining)
    - Grounding: Round concepts, difficulty, expected evidence, criteria, and candidate evidence gap analysis.
    - Safety: Respects untrusted data constraints and never replaces HR-authored questions silently.
    """
    mode = request.question_generation_mode.upper()
    results: list[InterviewPlanQuestionSchema] = []

    # 1. Mode: HR_DEFINED -> strictly use HR-authored questions
    if mode == "HR_DEFINED":
        for idx, q in enumerate(request.hr_questions, start=1):
            q_copy = q.model_copy()
            q_copy.sequence = idx
            q_copy.is_hr_authored = True
            q_copy.status = "APPROVED"
            results.append(q_copy)
        return results

    # 2. Mode: HYBRID -> preserve existing HR-authored questions first
    if mode == "HYBRID":
        for idx, q in enumerate(request.hr_questions, start=1):
            q_copy = q.model_copy()
            q_copy.sequence = idx
            q_copy.is_hr_authored = True
            q_copy.status = "APPROVED"
            results.append(q_copy)

    # Calculate remaining questions needed
    needed_count = max(1, request.target_count - len(results))
    existing_texts = {q.question_text.lower().strip() for q in results}

    # Fetch candidate pre-analysis for targeted evidence probing
    try:
        pre_analysis = await build_candidate_interview_pre_analysis(
            session=session,
            application_id=application_id,
            organization_id=organization_id,
        )
        claims_set = {c["capability_name"].lower() for c in pre_analysis.candidate_claims}
        unknown_set = {u["capability_name"].lower() for u in pre_analysis.candidate_unknowns}
    except Exception:
        claims_set = set()
        unknown_set = set()

    concepts = request.concepts if request.concepts else ["Core Fundamentals"]
    seq_start = len(results) + 1

    # Attempt AI question generation via LLM if available, else high-quality deterministic synthesis
    generated_questions: list[InterviewPlanQuestionSchema] = []
    if settings.groq_api_key and not settings.groq_api_key.startswith("your_"):
        try:
            llm_questions = await _llm_generate_round_questions(
                round_title=request.round_title,
                objective=request.objective,
                concepts=concepts,
                difficulty=request.difficulty,
                evaluation_criteria=request.evaluation_criteria,
                expected_evidence=request.expected_evidence,
                count=needed_count,
            )
            for lq in llm_questions:
                if lq.question_text.lower().strip() not in existing_texts:
                    generated_questions.append(lq)
                    existing_texts.add(lq.question_text.lower().strip())
                    if len(generated_questions) >= needed_count:
                        break
        except Exception as e:
            logger.warning(f"Groq question generation failed ({e}), falling back to grounded synthesis")

    # If LLM didn't produce enough questions, synthesize grounded questions
    for concept in concepts:
        if len(generated_questions) >= needed_count:
            break
        c_lower = concept.lower()

        if c_lower in claims_set:
            purpose = f"Validate resume claim on {concept} through production scenarios"
            ev_ver = f"{concept} (CLAIM)"
        elif c_lower in unknown_set:
            purpose = f"Probe foundational understanding and unverified capabilities in {concept}"
            ev_ver = f"{concept} (UNKNOWN)"
        else:
            purpose = f"Evaluate technical depth and implementation trade-offs in {concept}"
            ev_ver = f"{concept}"

        if request.difficulty.upper() == "HARD":
            text = f"Describe an instance where you optimized or diagnosed a bottleneck in {concept}. What trade-offs were made, and how did you verify the solution in production?"
            q_type = "SYSTEM_DESIGN"
        elif request.difficulty.upper() == "EASY":
            text = f"What are the foundational principles and standard design patterns associated with {concept} in modern software systems?"
            q_type = "CONCEPTUAL"
        else:
            text = f"Explain the architectural patterns, trade-offs, and practical design decisions you employ with {concept} in high-reliability applications."
            q_type = "PRACTICAL"

        if text.lower().strip() not in existing_texts:
            generated_questions.append(
                InterviewPlanQuestionSchema(
                    question_text=text,
                    concept=concept,
                    difficulty=request.difficulty.upper(),
                    question_type=q_type,
                    purpose=purpose,
                    evidence_being_verified=ev_ver,
                    is_hr_authored=False,
                    status="APPROVED",
                    sequence=seq_start + len(generated_questions),
                )
            )
            existing_texts.add(text.lower().strip())

    results.extend(generated_questions)
    for idx, q in enumerate(results, start=1):
        q.sequence = idx

    return results


async def _llm_generate_round_questions(
    round_title: str,
    objective: str,
    concepts: list[str],
    difficulty: str,
    evaluation_criteria: list[str],
    expected_evidence: list[str],
    count: int,
) -> list[InterviewPlanQuestionSchema]:
    """Generates structured questions via Groq with strict JSON output."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    system_prompt = """You are an expert technical hiring manager at Gap2Hire.
Generate focused, probing technical interview questions aligned to the specified round configuration.
Never invent candidate facts.
Output strictly valid JSON:
{
  "questions": [
    {
      "question_text": "...",
      "concept": "...",
      "difficulty": "EASY | MEDIUM | HARD",
      "question_type": "CONCEPTUAL | PRACTICAL | SYSTEM_DESIGN",
      "purpose": "What technical competency or claim this question verifies",
      "evidence_being_verified": "Concrete evidence expected"
    }
  ]
}"""

    user_prompt = f"""Round Title: {round_title}
Objective: {objective}
Concepts: {', '.join(concepts)}
Configured Difficulty: {difficulty}
Evaluation Criteria: {json.dumps(evaluation_criteria)}
Expected Evidence: {json.dumps(expected_evidence)}
Generate {count} distinct technical questions that evaluate these competencies."""

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        if res.status_code != 200:
            raise RuntimeError(f"Groq API returned {res.status_code}")
        data = res.json()
        raw_json = json.loads(data["choices"][0]["message"]["content"])
        qs = []
        for item in raw_json.get("questions", []):
            qs.append(
                InterviewPlanQuestionSchema(
                    question_text=item.get("question_text", ""),
                    concept=item.get("concept", concepts[0] if concepts else "Engineering"),
                    difficulty=item.get("difficulty", difficulty),
                    question_type=item.get("question_type", "CONCEPTUAL"),
                    purpose=item.get("purpose", f"Assess {concepts[0] if concepts else 'competency'}"),
                    evidence_being_verified=item.get("evidence_being_verified", concepts[0] if concepts else "Skills"),
                    is_hr_authored=False,
                    status="APPROVED",
                )
            )
        return qs
