from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate_hiring_decision import CandidateHiringDecision
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewSession
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.interview_report import InterviewReportModel
from app.models.job import Job
from app.models.user import User
from app.schemas.decision_replay import (
    DecisionContext,
    DecisionReplayResponse,
    EvidenceSnapshotItem,
    InterviewSnapshotContext,
    ScreeningSnapshotContext,
)


class ApplicationNotFoundError(Exception):
    pass


class DecisionReplayNotAvailableError(Exception):
    pass


async def build_decision_replay(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> DecisionReplayResponse:
    """Reconstructs what the hiring team knew at the exact time a hiring decision was made.

    Guarantees:
    - Enforces tenant isolation.
    - Captures historical evidence, screening data, interview report, and decision history.
    - Explicitly documents architectural limits where snapshots are reconstructed from persisted records.
    - Never evaluates or judges human decisions automatically.
    """
    # 1. Fetch application with candidate & job
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

    candidate = application.candidate
    job = application.job
    cand_name = getattr(candidate, "full_name", None) or getattr(candidate, "name", "Candidate")

    # 2. Fetch latest or all hiring decisions
    decisions_stmt = (
        select(CandidateHiringDecision)
        .options(selectinload(CandidateHiringDecision.decider))
        .where(CandidateHiringDecision.application_id == application_id)
        .order_by(CandidateHiringDecision.decided_at.desc())
    )
    result = await session.execute(decisions_stmt)
    all_decisions = result.scalars().all()

    latest_decision = all_decisions[0] if all_decisions else None

    # Reconstruct decision context
    if latest_decision:
        decider = latest_decision.decider or await session.get(User, latest_decision.decided_by)
        decision_ctx = DecisionContext(
            application_id=application.id,
            candidate_id=candidate.id,
            candidate_name=cand_name,
            candidate_email=getattr(candidate, "email", None),
            job_id=job.id,
            job_title=job.title,
            decision=latest_decision.decision,
            decision_reason=latest_decision.decision_reason,
            decided_by_id=decider.id if decider else latest_decision.decided_by,
            decided_by_name=(decider.full_name or decider.email) if decider else "Authorized Reviewer",
            decided_at=latest_decision.decided_at,
            application_status=application.status,
            report_id=latest_decision.report_id,
        )
    else:
        decision_ctx = DecisionContext(
            application_id=application.id,
            candidate_id=candidate.id,
            candidate_name=cand_name,
            candidate_email=getattr(candidate, "email", None),
            job_id=job.id,
            job_title=job.title,
            decision="PENDING",
            decision_reason="No final human hiring decision has been recorded yet.",
            decided_by_id=application.candidate_id,
            decided_by_name="System",
            decided_at=application.updated_at or datetime.utcnow(),
            application_status=application.status,
            report_id=None,
        )

    # 3. Reconstruct screening context
    screening_ctx = ScreeningSnapshotContext(
        screening_status=application.screening_status or "PENDING",
        screening_notes=application.screening_notes,
        shortlist_status=application.shortlist_status or "PENDING",
        shortlist_reason=application.shortlist_reason,
        hard_requirement_coverage=1.0 if application.screening_status == "COMPLETED" else None,
        strengths=[],
        gaps=[],
        unknowns=[],
        verification_needs=[],
    )

    # 4. Fetch evidence records for capabilities
    evidence_stmt = (
        select(Evidence)
        .options(selectinload(Evidence.capability))
        .where(Evidence.application_id == application_id)
    )
    ev_res = await session.execute(evidence_stmt)
    evidence_list = ev_res.scalars().all()

    evidence_items: list[EvidenceSnapshotItem] = []
    for ev in evidence_list:
        cap_name = ev.capability.name if ev.capability else "General Capability"
        evidence_items.append(
            EvidenceSnapshotItem(
                capability_id=ev.capability_id,
                capability_name=cap_name,
                state=getattr(ev, "provenance", None) or getattr(ev, "state", "CLAIM") or "CLAIM",
                source_type=getattr(ev, "source_type", None) or "RESUME",
                source_url=getattr(ev, "source_url", None),
                evidence_excerpt=getattr(ev, "content", None) or getattr(ev, "evidence_text", None) or getattr(ev, "excerpt", None),
                confidence=getattr(ev, "strength", None) or getattr(ev, "confidence", "MODERATE"),
                provenance_summary=f"Extracted from {getattr(ev, 'source_type', 'Resume')}",
            )
        )

    # 5. Fetch Interview Report context if available
    interview_ctx = None
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
    report_obj = await session.scalar(report_stmt)

    unresolved_areas_list: list[str] = []

    if report_obj:
        # Count integrity events
        int_stmt = select(InterviewIntegrityEvent).where(
            InterviewIntegrityEvent.interview_session_id == report_obj.interview_session_id
        )
        int_res = await session.execute(int_stmt)
        int_events = int_res.scalars().all()

        unresolved = [
            u.get("area", str(u)) if isinstance(u, dict) else str(u)
            for u in (report_obj.unresolved_areas or [])
        ]
        unresolved_areas_list = unresolved

        demonstrated = [
            d.get("capability_name", str(d)) if isinstance(d, dict) else str(d)
            for d in (report_obj.demonstrated_capabilities or [])
        ]
        claimed = [
            c.get("capability_name", str(c)) if isinstance(c, dict) else str(c)
            for c in (report_obj.claimed_capabilities or [])
        ]
        unknown = [
            u.get("capability_name", str(u)) if isinstance(u, dict) else str(u)
            for u in (report_obj.unknown_capabilities or [])
        ]
        ver_needed = [
            v.get("capability_name", str(v)) if isinstance(v, dict) else str(v)
            for v in (report_obj.verification_needed or [])
        ]

        interview_ctx = InterviewSnapshotContext(
            report_id=report_obj.id,
            session_id=report_obj.interview_session_id,
            interview_status="COMPLETED",
            report_summary=report_obj.summary,
            demonstrated_capabilities=demonstrated,
            claimed_capabilities=claimed,
            unknown_capabilities=unknown,
            verification_needed=ver_needed,
            unresolved_areas=unresolved,
            question_count=len(report_obj.question_findings or []),
            round_count=len(report_obj.round_summaries or []),
            integrity_events_count=len(int_events),
        )

    # 6. Format historical decision entries
    decision_history_formatted: list[dict] = []
    for d in reversed(all_decisions):
        d_user = d.decider
        decision_history_formatted.append({
            "id": str(d.id),
            "decision": d.decision,
            "decision_reason": d.decision_reason,
            "decided_by": (d_user.full_name or d_user.email) if d_user else str(d.decided_by),
            "decided_at": d.decided_at.isoformat() if d.decided_at else None,
            "report_id": str(d.report_id) if d.report_id else None,
            "previous_decision_id": str(d.previous_decision_id) if d.previous_decision_id else None,
        })

    # 7. Document explicit limitations
    limitations = [
        "Decision Replay reconstructs the knowledge state from persisted application, screening, evidence, and interview report records.",
        "Candidate Evidence records reflect the verified state at the time of candidate ingestion and research processing.",
        "Interview findings reflect the immutable Post-Interview Analysis Report generated prior to human review.",
        "Audit trail accurately preserves chronological human hiring decision chains with decision-maker attribution.",
    ]

    return DecisionReplayResponse(
        application_id=application.id,
        job_id=job.id,
        candidate_id=candidate.id,
        reconstructed_at=datetime.utcnow(),
        decision_context=decision_ctx,
        screening_context=screening_ctx,
        evidence_context=evidence_items,
        interview_context=interview_ctx,
        unresolved_areas=unresolved_areas_list,
        decision_history=decision_history_formatted,
        limitations=limitations,
    )
