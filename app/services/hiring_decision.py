from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_hiring_decision import CandidateHiringDecision
from app.models.interview import InterviewSession
from app.models.interview_report import InterviewReportModel
from app.models.job import Job
from app.models.user import User
from app.schemas.hiring_decision import (
    HiringDecisionCreate,
    HiringDecisionHistoryResponse,
    HiringDecisionResponse,
    HiringDecisionType,
)


class ApplicationNotFoundError(Exception):
    pass


class InvalidDecisionError(Exception):
    pass


class InvalidDecisionReasonError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


VALID_HIRING_DECISIONS = {
    HiringDecisionType.SELECTED.value,
    HiringDecisionType.REJECTED.value,
    HiringDecisionType.ON_HOLD.value,
}


def _build_hiring_decision_response(
    decision_obj: CandidateHiringDecision,
    application: Application,
    job: Job,
    candidate: Candidate,
    decider: User,
) -> HiringDecisionResponse:
    cand_name = getattr(candidate, "full_name", None) or getattr(candidate, "name", "Candidate")
    return HiringDecisionResponse(
        id=decision_obj.id,
        application_id=decision_obj.application_id,
        candidate_id=candidate.id,
        candidate_name=cand_name,
        candidate_email=getattr(candidate, "email", None),
        job_id=job.id,
        job_title=job.title,
        decision=decision_obj.decision,
        decision_reason=decision_obj.decision_reason,
        decided_by=decider.id,
        decided_by_name=decider.full_name or decider.email,
        decided_by_email=decider.email,
        decided_at=decision_obj.decided_at,
        report_id=decision_obj.report_id,
        previous_decision_id=decision_obj.previous_decision_id,
        application_status=application.status,
        metadata=decision_obj.metadata_json or {},
        created_at=decision_obj.created_at or decision_obj.decided_at or datetime.utcnow(),
    )


async def record_human_hiring_decision(
    session: AsyncSession,
    application_id: UUID,
    user: User,
    data: HiringDecisionCreate,
    metadata: dict[str, Any] | None = None,
) -> HiringDecisionResponse:
    """Records an authorized human recruiter or hiring manager hiring decision.

    Guarantees:
    - AI does NOT make or automate the decision.
    - Tenant isolation is strictly enforced.
    - Reason is human-supplied, non-empty, and validated.
    - Preserves audit history with previous decision linkage.
    - Updates application lifecycle appropriately.
    """
    decision_clean = data.decision.value.upper() if hasattr(data.decision, "value") else str(data.decision).upper()
    if decision_clean not in VALID_HIRING_DECISIONS:
        raise InvalidDecisionError(
            f"Invalid decision '{data.decision}'. Must be one of: {', '.join(sorted(VALID_HIRING_DECISIONS))}"
        )

    reason_clean = (data.decision_reason or "").strip()
    if not reason_clean or len(reason_clean) < 5:
        raise InvalidDecisionReasonError(
            "A meaningful human decision reason is required (minimum 5 characters)."
        )

    # 1. Fetch application and verify tenant isolation
    stmt = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == user.organization_id,
        )
    )
    application = await session.scalar(stmt)
    if not application:
        raise ApplicationNotFoundError("Application not found or inaccessible under current tenant.")

    job = application.job
    candidate = application.candidate

    # 2. Look up the most recent completed interview report for this application (if any)
    report_stmt = (
        select(InterviewReportModel)
        .join(InterviewSession, InterviewSession.id == InterviewReportModel.interview_session_id)
        .where(
            InterviewSession.application_id == application_id,
            InterviewReportModel.status == "COMPLETED",
        )
        .order_by(InterviewReportModel.created_at.desc())
        .limit(1)
    )
    latest_report = await session.scalar(report_stmt)

    # 3. Find previous decision record for history audit chaining
    prev_stmt = (
        select(CandidateHiringDecision)
        .where(CandidateHiringDecision.application_id == application_id)
        .order_by(CandidateHiringDecision.decided_at.desc())
        .limit(1)
    )
    previous_decision = await session.scalar(prev_stmt)

    # 4. Create new decision record
    now = datetime.utcnow()
    decision_record = CandidateHiringDecision(
        id=uuid4(),
        application_id=application.id,
        job_id=job.id,
        decision=decision_clean,
        decision_reason=reason_clean,
        decided_by=user.id,
        decided_at=now,
        report_id=latest_report.id if latest_report else None,
        previous_decision_id=previous_decision.id if previous_decision else None,
        metadata_json=metadata or {},
        created_at=now,
        updated_at=now,
    )
    session.add(decision_record)

    # 5. Update application lifecycle
    application.status = decision_clean
    application.shortlist_status = decision_clean
    application.shortlist_reason = reason_clean
    if decision_clean == HiringDecisionType.SELECTED.value:
        application.shortlisted_at = now
    application.updated_at = now

    await session.commit()
    await session.refresh(decision_record)

    return _build_hiring_decision_response(
        decision_obj=decision_record,
        application=application,
        job=job,
        candidate=candidate,
        decider=user,
    )


async def get_application_hiring_decisions(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> HiringDecisionHistoryResponse:
    """Retrieves full chronological hiring decision history for an application."""
    # 1. Verify application & tenant access
    stmt = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(stmt)
    if not application:
        raise ApplicationNotFoundError("Application not found or inaccessible under current tenant.")

    job = application.job
    candidate = application.candidate

    # 2. Fetch all decisions for this application in chronological order
    decisions_stmt = (
        select(CandidateHiringDecision)
        .options(selectinload(CandidateHiringDecision.decider))
        .where(CandidateHiringDecision.application_id == application_id)
        .order_by(CandidateHiringDecision.decided_at.asc())
    )
    result = await session.execute(decisions_stmt)
    decision_records = result.scalars().all()

    history_items: list[HiringDecisionResponse] = []
    for rec in decision_records:
        decider_user = rec.decider or await session.get(User, rec.decided_by)
        history_items.append(
            _build_hiring_decision_response(
                decision_obj=rec,
                application=application,
                job=job,
                candidate=candidate,
                decider=decider_user,
            )
        )

    current_decision = history_items[-1] if history_items else None
    cand_name = (
        f"{candidate.first_name} {candidate.last_name}".strip()
        if hasattr(candidate, "first_name") and hasattr(candidate, "last_name")
        else getattr(candidate, "name", "Candidate")
    )

    return HiringDecisionHistoryResponse(
        application_id=application.id,
        candidate_id=candidate.id,
        candidate_name=cand_name,
        current_decision=current_decision,
        history=history_items,
        total_decisions=len(history_items),
    )


async def get_latest_application_hiring_decision(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> HiringDecisionResponse | None:
    """Retrieves the latest hiring decision for an application if one exists."""
    history_resp = await get_application_hiring_decisions(
        session=session,
        application_id=application_id,
        organization_id=organization_id,
    )
    return history_resp.current_decision
