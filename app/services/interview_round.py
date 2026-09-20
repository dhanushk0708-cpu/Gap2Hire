from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.capability import Capability
from app.models.interview_round import InterviewQuestionTemplate, InterviewRound
from app.models.job import Job
from app.schemas.interview_question_template import (
    InterviewQuestionTemplateCreate,
    InterviewQuestionTemplateUpdate,
)
from app.schemas.interview_round import (
    InterviewRoundCreate,
    InterviewRoundUpdate,
)


class JobNotFoundError(Exception):
    pass


class RoundNotFoundError(Exception):
    pass


class QuestionTemplateNotFoundError(Exception):
    pass


class InvalidCapabilityForJobError(Exception):
    pass


class DuplicateSequenceError(Exception):
    pass


async def get_tenant_job(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> Job | None:
    stmt = select(Job).where(
        Job.id == job_id,
        Job.organization_id == organization_id,
    )
    return await session.scalar(stmt)


async def create_interview_round(
    session: AsyncSession,
    job_id: UUID,
    round_in: InterviewRoundCreate,
    organization_id: UUID,
) -> InterviewRound:
    job = await get_tenant_job(session, job_id, organization_id)
    if job is None:
        raise JobNotFoundError("Job not found or inaccessible")

    # Check sequence uniqueness for this job
    seq_stmt = select(InterviewRound).where(
        InterviewRound.job_id == job_id,
        InterviewRound.sequence == round_in.sequence,
    )
    existing = await session.scalar(seq_stmt)
    if existing is not None:
        raise DuplicateSequenceError(f"A round with sequence {round_in.sequence} already exists for this job")

    interview_round = InterviewRound(
        job_id=job_id,
        name=round_in.name,
        round_type=round_in.round_type.value,
        sequence=round_in.sequence,
        description=round_in.description,
        status="ACTIVE",
    )
    session.add(interview_round)
    await session.commit()
    await session.refresh(interview_round)
    return interview_round


async def list_interview_rounds_for_job(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> list[InterviewRound]:
    job = await get_tenant_job(session, job_id, organization_id)
    if job is None:
        raise JobNotFoundError("Job not found or inaccessible")

    stmt = (
        select(InterviewRound)
        .where(InterviewRound.job_id == job_id)
        .order_by(InterviewRound.sequence.asc())
    )
    return list((await session.scalars(stmt)).all())


async def get_interview_round_by_id(
    session: AsyncSession,
    round_id: UUID,
    organization_id: UUID,
) -> InterviewRound | None:
    stmt = (
        select(InterviewRound)
        .join(Job, Job.id == InterviewRound.job_id)
        .where(
            InterviewRound.id == round_id,
            Job.organization_id == organization_id,
        )
        .options(selectinload(InterviewRound.question_templates))
    )
    return await session.scalar(stmt)


async def update_interview_round(
    session: AsyncSession,
    round_id: UUID,
    round_in: InterviewRoundUpdate,
    organization_id: UUID,
) -> InterviewRound:
    interview_round = await get_interview_round_by_id(session, round_id, organization_id)
    if interview_round is None:
        raise RoundNotFoundError("Interview round not found or inaccessible")

    if round_in.sequence is not None and round_in.sequence != interview_round.sequence:
        seq_stmt = select(InterviewRound).where(
            InterviewRound.job_id == interview_round.job_id,
            InterviewRound.sequence == round_in.sequence,
            InterviewRound.id != round_id,
        )
        if await session.scalar(seq_stmt) is not None:
            raise DuplicateSequenceError(f"A round with sequence {round_in.sequence} already exists")
        interview_round.sequence = round_in.sequence

    if round_in.name is not None:
        interview_round.name = round_in.name
    if round_in.round_type is not None:
        interview_round.round_type = round_in.round_type.value
    if round_in.description is not None:
        interview_round.description = round_in.description
    if round_in.status is not None:
        interview_round.status = round_in.status

    await session.commit()
    await session.refresh(interview_round)
    return interview_round


async def delete_interview_round(
    session: AsyncSession,
    round_id: UUID,
    organization_id: UUID,
) -> None:
    interview_round = await get_interview_round_by_id(session, round_id, organization_id)
    if interview_round is None:
        raise RoundNotFoundError("Interview round not found or inaccessible")

    await session.delete(interview_round)
    await session.commit()


# --- Question Templates ---

async def create_question_template(
    session: AsyncSession,
    round_id: UUID,
    template_in: InterviewQuestionTemplateCreate,
    organization_id: UUID,
    user_id: UUID | None = None,
) -> InterviewQuestionTemplate:
    interview_round = await get_interview_round_by_id(session, round_id, organization_id)
    if interview_round is None:
        raise RoundNotFoundError("Interview round not found or inaccessible")

    # If capability_id is provided, verify it belongs to the round's job
    if template_in.capability_id is not None:
        cap_stmt = select(Capability).where(
            Capability.id == template_in.capability_id,
            Capability.job_id == interview_round.job_id,
        )
        if await session.scalar(cap_stmt) is None:
            raise InvalidCapabilityForJobError("Capability does not belong to the job associated with this round")

    # Check sequence uniqueness in this round
    seq_stmt = select(InterviewQuestionTemplate).where(
        InterviewQuestionTemplate.round_id == round_id,
        InterviewQuestionTemplate.sequence == template_in.sequence,
    )
    if await session.scalar(seq_stmt) is not None:
        raise DuplicateSequenceError(f"A question template with sequence {template_in.sequence} already exists in this round")

    template = InterviewQuestionTemplate(
        round_id=round_id,
        capability_id=template_in.capability_id,
        question_intent=template_in.question_intent.value,
        question_text=template_in.question_text,
        difficulty=template_in.difficulty.value,
        required=template_in.required,
        max_followups=template_in.max_followups,
        sequence=template_in.sequence,
        created_by=user_id,
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def list_question_templates_for_round(
    session: AsyncSession,
    round_id: UUID,
    organization_id: UUID,
) -> list[InterviewQuestionTemplate]:
    interview_round = await get_interview_round_by_id(session, round_id, organization_id)
    if interview_round is None:
        raise RoundNotFoundError("Interview round not found or inaccessible")

    stmt = (
        select(InterviewQuestionTemplate)
        .where(InterviewQuestionTemplate.round_id == round_id)
        .order_by(InterviewQuestionTemplate.sequence.asc())
    )
    return list((await session.scalars(stmt)).all())


async def get_question_template_by_id(
    session: AsyncSession,
    template_id: UUID,
    organization_id: UUID,
) -> InterviewQuestionTemplate | None:
    stmt = (
        select(InterviewQuestionTemplate)
        .join(InterviewRound, InterviewRound.id == InterviewQuestionTemplate.round_id)
        .join(Job, Job.id == InterviewRound.job_id)
        .where(
            InterviewQuestionTemplate.id == template_id,
            Job.organization_id == organization_id,
        )
    )
    return await session.scalar(stmt)


async def update_question_template(
    session: AsyncSession,
    template_id: UUID,
    template_in: InterviewQuestionTemplateUpdate,
    organization_id: UUID,
) -> InterviewQuestionTemplate:
    template = await get_question_template_by_id(session, template_id, organization_id)
    if template is None:
        raise QuestionTemplateNotFoundError("Question template not found or inaccessible")

    # If updating capability_id, check job match
    if template_in.capability_id is not None:
        round_stmt = select(InterviewRound).where(InterviewRound.id == template.round_id)
        current_round = await session.scalar(round_stmt)
        if current_round is not None:
            cap_stmt = select(Capability).where(
                Capability.id == template_in.capability_id,
                Capability.job_id == current_round.job_id,
            )
            if await session.scalar(cap_stmt) is None:
                raise InvalidCapabilityForJobError("Capability does not belong to the job associated with this round")
        template.capability_id = template_in.capability_id

    if template_in.sequence is not None and template_in.sequence != template.sequence:
        seq_stmt = select(InterviewQuestionTemplate).where(
            InterviewQuestionTemplate.round_id == template.round_id,
            InterviewQuestionTemplate.sequence == template_in.sequence,
            InterviewQuestionTemplate.id != template_id,
        )
        if await session.scalar(seq_stmt) is not None:
            raise DuplicateSequenceError(f"A question template with sequence {template_in.sequence} already exists in this round")
        template.sequence = template_in.sequence

    if template_in.question_intent is not None:
        template.question_intent = template_in.question_intent.value
    if template_in.question_text is not None:
        template.question_text = template_in.question_text
    if template_in.difficulty is not None:
        template.difficulty = template_in.difficulty.value
    if template_in.required is not None:
        template.required = template_in.required
    if template_in.max_followups is not None:
        template.max_followups = template_in.max_followups

    await session.commit()
    await session.refresh(template)
    return template


async def delete_question_template(
    session: AsyncSession,
    template_id: UUID,
    organization_id: UUID,
) -> None:
    template = await get_question_template_by_id(session, template_id, organization_id)
    if template is None:
        raise QuestionTemplateNotFoundError("Question template not found or inaccessible")

    await session.delete(template)
    await session.commit()
