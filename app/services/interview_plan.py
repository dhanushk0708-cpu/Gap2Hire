from datetime import datetime
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    InterviewPlanResponse,
    InterviewPlanRoundSchema,
    InterviewPlanUpdateRequest,
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
    - Selects relevant questions from the uploaded question datasets.
    - Prevents duplicate questions across the candidate's entire plan.
    - Preserves dataset_question_id references.
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
        # Default to the most recent dataset file for the job or organization
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
        status="DRAFT",
        candidate_strengths_summary=strengths_summary,
        verification_targets_summary=targets_summary,
        created_by=created_by,
    )
    session.add(plan)

    # Question selection state to guarantee zero duplicate questions
    used_question_ids: set[UUID] = set()
    used_question_texts: set[str] = set()

    # Determine round concepts based on candidate strengths, claims, and unknowns
    claims_concepts = [c["capability_name"] for c in pre_analysis.candidate_claims]
    demonstrated_concepts = [s["capability_name"] for s in pre_analysis.candidate_strengths]
    unknown_concepts = [u["capability_name"] for u in pre_analysis.candidate_unknowns]

    # ROUND 1: Core Fundamentals & Primary Claims
    # Focus: Verify resume claims and foundational technical skills
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
        concepts=round1_concepts,
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
    # Focus: Probe UNKNOWN / INSUFFICIENT capabilities and advanced implementation
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
        concepts=round2_concepts,
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
    # Focus: Real projects, architecture decisions, trade-offs, debugging
    round3_concepts = pre_analysis.relevant_concepts[:3] if pre_analysis.relevant_concepts else ["Architecture", "System Design"]
    round3 = InterviewPlanRound(
        id=uuid4(),
        plan_id=plan.id,
        round_number=3,
        title="Round 3 — Practical Architecture & Production Decisions",
        objective="Examine candidate's real project architecture, design trade-offs, and production troubleshooting decisions.",
        concepts=round3_concepts,
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

    # Candidate claims map for purpose explanation
    claims_set = {c["capability_name"].lower() for c in pre_analysis.candidate_claims}
    unknown_set = {u["capability_name"].lower() for u in pre_analysis.candidate_unknowns}
    demonstrated_set = {s["capability_name"].lower() for s in pre_analysis.candidate_strengths}

    for concept in concepts:
        c_lower = concept.lower()
        # Find matching questions in dataset
        pool = questions_by_concept.get(c_lower, [])
        if not pool:
            # Fallback search across concepts
            pool = [q for k, qs in questions_by_concept.items() if c_lower in k for q in qs]

        for q in pool:
            if q.id in used_question_ids or q.question_text.lower() in used_question_texts:
                continue

            # Determine purpose based on candidate state
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
        return plan  # Idempotent approval

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
    Allows HR user to edit rounds, objectives, durations, and questions on a draft plan.
    If the plan is already APPROVED, editing is rejected (an approved plan must be versioned/regenerated).
    """
    plan = await get_interview_plan(session, organization_id, plan_id)

    if plan.status == "APPROVED":
        raise InvalidPlanStateError("Cannot modify an already approved interview plan. Please regenerate a new version.")

    if data.hr_feedback is not None:
        plan.hr_feedback = data.hr_feedback

    # Replace rounds & questions with updated values
    plan.rounds.clear()
    await session.flush()

    for r_idx, r_data in enumerate(data.rounds, start=1):
        round_obj = InterviewPlanRound(
            id=uuid4(),
            plan_id=plan.id,
            round_number=r_data.round_number or r_idx,
            title=r_data.title,
            objective=r_data.objective,
            concepts=r_data.concepts,
            estimated_duration_minutes=r_data.estimated_duration_minutes,
            required=r_data.required,
            reasoning=r_data.reasoning,
            sequence=r_idx,
        )
        plan.rounds.append(round_obj)

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
                sequence=q_idx,
            )
            round_obj.questions.append(q_obj)

    target_plan_id = plan.id
    plan.updated_at = datetime.utcnow()
    await session.commit()
    return await get_interview_plan(session, organization_id, target_plan_id)
