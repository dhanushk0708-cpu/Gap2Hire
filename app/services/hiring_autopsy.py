from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate_hiring_decision import CandidateHiringDecision
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewSession
from app.models.interview_report import InterviewReportModel
from app.models.job import Job
from app.models.post_hire_outcome import PostHireOutcome
from app.models.user import User
from app.schemas.hiring_autopsy import (
    AIImprovementSuggestion,
    AutopsyFinding,
    CapabilityOutcomeComparison,
    HiringAutopsyResponse,
)
from app.schemas.post_hire_outcome import PostHireOutcomeResponse


class ApplicationNotFoundError(Exception):
    pass


async def build_hiring_autopsy(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> HiringAutopsyResponse:
    """Generates an evidence-grounded Hiring Autopsy comparing hiring expectations vs post-hire work observations."""
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

    # 2. Fetch latest decision
    dec_stmt = (
        select(CandidateHiringDecision)
        .options(selectinload(CandidateHiringDecision.decider))
        .where(CandidateHiringDecision.application_id == application_id)
        .order_by(CandidateHiringDecision.decided_at.desc())
        .limit(1)
    )
    latest_decision = await session.scalar(dec_stmt)

    decision_summary = {
        "status": application.status,
        "decision": latest_decision.decision if latest_decision else "PENDING",
        "reason": latest_decision.decision_reason if latest_decision else None,
        "decided_by": (latest_decision.decider.full_name or latest_decision.decider.email) if (latest_decision and latest_decision.decider) else None,
        "decided_at": latest_decision.decided_at.isoformat() if latest_decision else None,
    }

    # 3. Fetch interview report
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

    # 4. Fetch pre-hire evidence
    ev_stmt = (
        select(Evidence)
        .options(selectinload(Evidence.capability))
        .where(Evidence.application_id == application_id)
    )
    ev_res = await session.execute(ev_stmt)
    ev_list = ev_res.scalars().all()
    evidence_by_cap: dict[str, str] = {}
    for e in ev_list:
        name = e.capability.name if e.capability else "General"
        evidence_by_cap[name.lower()] = getattr(e, "provenance", None) or getattr(e, "state", "CLAIM") or "CLAIM"

    # 5. Fetch post-hire outcomes
    outcomes_stmt = (
        select(PostHireOutcome)
        .options(selectinload(PostHireOutcome.recorder))
        .where(PostHireOutcome.application_id == application_id)
        .order_by(PostHireOutcome.recorded_at.asc())
    )
    outcomes_res = await session.execute(outcomes_stmt)
    outcomes_list = outcomes_res.scalars().all()

    outcomes_by_cap: dict[str, PostHireOutcome] = {}
    post_hire_resp_list: list[PostHireOutcomeResponse] = []
    for o in outcomes_list:
        outcomes_by_cap[o.capability_name.lower()] = o
        rec_user = o.recorder or await session.get(User, o.recorded_by)
        post_hire_resp_list.append(
            PostHireOutcomeResponse(
                id=o.id,
                application_id=o.application_id,
                job_id=job.id,
                job_title=job.title,
                candidate_id=candidate.id,
                candidate_name=cand_name,
                recorded_by=o.recorded_by,
                recorded_by_name=(rec_user.full_name or rec_user.email) if rec_user else "Hiring Manager",
                recorded_at=o.recorded_at,
                outcome_period=o.outcome_period,
                capability_id=o.capability_id,
                capability_name=o.capability_name,
                expected_capability_description=o.expected_capability_description,
                observed_outcome_description=o.observed_outcome_description,
                outcome_status=o.outcome_status,
                manager_notes=o.manager_notes,
                evidence_reference=o.evidence_reference,
                metadata=o.metadata_json or {},
                created_at=o.created_at or o.recorded_at,
            )
        )

    # 6. Fetch Job Capabilities
    caps_stmt = select(Capability).where(Capability.job_id == job.id)
    caps_res = await session.execute(caps_stmt)
    job_caps = caps_res.scalars().all()

    # Map interview findings
    interview_demonstrated_caps = set()
    interview_unknown_caps = set()
    interview_weakness_caps = set()

    if report_obj:
        for d in (report_obj.demonstrated_capabilities or []):
            name = d.get("capability_name", str(d)) if isinstance(d, dict) else str(d)
            interview_demonstrated_caps.add(name.lower())
        for u in (report_obj.unknown_capabilities or []):
            name = u.get("capability_name", str(u)) if isinstance(u, dict) else str(u)
            interview_unknown_caps.add(name.lower())
        for v in (report_obj.verification_needed or []):
            name = v.get("capability_name", str(v)) if isinstance(v, dict) else str(v)
            interview_unknown_caps.add(name.lower())

    # Build capability comparisons, findings, and suggestions
    comparisons: list[CapabilityOutcomeComparison] = []
    findings: list[AutopsyFinding] = []
    suggestions: list[AIImprovementSuggestion] = []

    all_cap_names = {c.name for c in job_caps}
    for o in outcomes_list:
        all_cap_names.add(o.capability_name)

    for cap_name in sorted(all_cap_names):
        cap_key = cap_name.lower()
        pre_state = evidence_by_cap.get(cap_key, "UNKNOWN")

        # Interview state
        if cap_key in interview_demonstrated_caps:
            interview_state = "DEMONSTRATED_STRONG"
        elif cap_key in interview_unknown_caps:
            interview_state = "UNTESTED_OR_INSUFFICIENT"
        else:
            interview_state = "NOT_EVALUATED"

        # Post-hire state
        outcome_obj = outcomes_by_cap.get(cap_key)
        outcome_status = outcome_obj.outcome_status if outcome_obj else None

        if outcome_status:
            if outcome_status == "NEEDS_DEVELOPMENT":
                if interview_state in ("UNTESTED_OR_INSUFFICIENT", "NOT_EVALUATED") or pre_state in ("UNKNOWN", "CLAIM"):
                    delta_text = f"Observed outcome indicated additional development needed for {cap_name}, which was marked {pre_state} during hiring without live practical verification."
                    findings.append(
                        AutopsyFinding(
                            category="UNVERIFIED_CAPABILITY",
                            affected_capability=cap_name,
                            finding_text=f"{cap_name} lacked live practical verification during hiring and subsequently required post-hire development support.",
                            grounded_facts=[
                                f"Pre-hire evidence state: {pre_state}",
                                f"Interview evaluation status: {interview_state}",
                                f"Observed outcome: {outcome_obj.observed_outcome_description}",
                            ],
                        )
                    )
                    suggestions.append(
                        AIImprovementSuggestion(
                            suggestion_id=f"sug-{len(suggestions) + 1}",
                            affected_capability=cap_name,
                            observed_pattern=f"{cap_name} was {pre_state} pre-hire and not deeply probed in the interview.",
                            suggested_improvement=f"Add a targeted live coding exercise or practical scenario verification for {cap_name} in future interview rounds.",
                            action_type="ADD_VERIFICATION_STEP",
                            confidence_strength="HIGH_CONFIDENCE",
                            supporting_records=[
                                f"Job: {job.title}",
                                f"Pre-hire state: {pre_state}",
                                f"Post-hire outcome: {outcome_status}",
                            ],
                        )
                    )
                else:
                    delta_text = f"Observed work outcome differed from positive interview demonstration in {cap_name}."
                    findings.append(
                        AutopsyFinding(
                            category="OUTCOME_DIVERGENCE",
                            affected_capability=cap_name,
                            finding_text=f"Demonstrated interview proficiency in {cap_name} differed from on-the-job execution observations.",
                            grounded_facts=[
                                f"Interview state: {interview_state}",
                                f"Observed outcome: {outcome_obj.observed_outcome_description}",
                            ],
                        )
                    )
                    suggestions.append(
                        AIImprovementSuggestion(
                            suggestion_id=f"sug-{len(suggestions) + 1}",
                            affected_capability=cap_name,
                            observed_pattern=f"Discrepancy between interview Q&A and practical execution for {cap_name}.",
                            suggested_improvement=f"Incorporate real-world codebase debugging or repository artifact review for {cap_name}.",
                            action_type="EXPAND_INTERVIEW_QUESTIONS",
                            confidence_strength="MODERATE_CONFIDENCE",
                            supporting_records=[f"Outcome: {outcome_status}"],
                        )
                    )
            elif outcome_status == "MEETS_EXPECTATION":
                delta_text = f"Observed work outcome confirmed expected capabilities for {cap_name}."
            else:
                delta_text = f"Post-hire observation status for {cap_name}: {outcome_status}."
        else:
            delta_text = f"No post-hire outcome recorded yet for {cap_name}."

        comparisons.append(
            CapabilityOutcomeComparison(
                capability_name=cap_name,
                pre_hire_evidence_state=pre_state,
                interview_demonstration_state=interview_state,
                post_hire_outcome_status=outcome_status or "NO_DATA",
                outcome_delta_observation=delta_text,
            )
        )

    # General fallback suggestion if no specific gaps were triggered
    if not suggestions:
        suggestions.append(
            AIImprovementSuggestion(
                suggestion_id="sug-baseline-1",
                affected_capability="General Hiring Pipeline",
                observed_pattern="Hiring evidence and work outcomes demonstrate strong alignment across evaluated core requirements.",
                suggested_improvement="Maintain current multi-round interview rubric and continue collecting 90-day post-hire feedback.",
                action_type="UPDATE_CAPABILITY_BLUEPRINT",
                confidence_strength="HIGH_CONFIDENCE",
                supporting_records=[f"Application {application.id}"],
            )
        )

    decision_replay_summary = {
        "candidate_name": cand_name,
        "job_title": job.title,
        "total_capabilities_evaluated": len(comparisons),
        "total_post_hire_outcomes": len(outcomes_list),
        "total_interview_questions": len(report_obj.question_findings or []) if report_obj else 0,
    }

    limitations = [
        "Hiring Autopsy is an organizational learning tool that identifies process improvement opportunities.",
        "It does not evaluate whether individual humans made correct or incorrect hiring decisions.",
        "AI suggestions are purely advisory and do not automatically alter job blueprints, interview plans, or hiring decisions.",
    ]

    return HiringAutopsyResponse(
        application_id=application.id,
        job_id=job.id,
        job_title=job.title,
        candidate_id=candidate.id,
        candidate_name=cand_name,
        decision_summary=decision_summary,
        decision_replay_summary=decision_replay_summary,
        post_hire_outcomes=post_hire_resp_list,
        capability_comparison=comparisons,
        findings=findings,
        ai_improvement_suggestions=suggestions,
        limitations=limitations,
    )
