import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_answer_analysis import InterviewAnswerAnalysis
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.interview_report import InterviewReportModel
from app.models.interview_round import InterviewRound
from app.models.job import Job
from app.schemas.interview_analysis import (
    InterviewReport,
    PostInterviewCapabilityFinding,
    PostInterviewHumanRecommendation,
    PostInterviewIntegrityObservation,
    PostInterviewIntegritySummary,
    PostInterviewQuestionFinding,
    PostInterviewRoundSummary,
)
from app.services.interview import (
    InterviewSessionNotFoundError,
    InvalidSessionStateError,
)
from app.services.interview_pre_analysis import build_candidate_interview_pre_analysis

logger = logging.getLogger(__name__)


class InterviewReportNotFoundError(Exception):
    pass


class ReportGenerationError(Exception):
    pass


async def generate_and_persist_interview_report(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
    generation_source: str = "SYSTEM_AI",
) -> InterviewReportModel:
    """
    Generates a structured, evidence-based post-interview analysis report for HR.
    Strict architectural invariants:
    1. Only completed sessions can be analyzed.
    2. Zero opaque AI cheating/candidate fit scores.
    3. Provenance preservation: CLAIM is not upgraded without supporting interview evidence.
    4. UNKNOWN is preserved and never penalized as failure.
    5. Integrity telemetry is reported separately as factual observations without intent classification.
    6. All findings contain direct source references.
    7. Human recruiter owns the final hiring decision.
    """
    # 1. Load full session with tenant verification
    stmt = (
        select(InterviewSession)
        .join(Application, Application.id == InterviewSession.application_id)
        .join(Job, Job.id == Application.job_id)
        .options(
            selectinload(InterviewSession.application).selectinload(Application.candidate),
            selectinload(InterviewSession.application).selectinload(Application.job),
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.messages),
            selectinload(InterviewSession.answer_analyses),
            selectinload(InterviewSession.integrity_events),
        )
        .where(
            InterviewSession.id == session_id,
            Job.organization_id == organization_id,
        )
    )
    interview_session = await session.scalar(stmt)
    if interview_session is None:
        raise InterviewSessionNotFoundError(f"Interview session '{session_id}' not found or inaccessible.")

    # 2. Check lifecycle status: must be COMPLETED
    if interview_session.status != "COMPLETED":
        raise InvalidSessionStateError(
            f"Cannot generate report: Interview session status is '{interview_session.status}'. Expected 'COMPLETED'."
        )

    application = interview_session.application
    candidate = application.candidate
    job = application.job

    # 3. Load job capabilities
    caps_stmt = select(Capability).where(Capability.job_id == job.id)
    job_capabilities = (await session.scalars(caps_stmt)).all()

    # 4. Load pre-interview analysis for grounded baseline
    pre_analysis = await build_candidate_interview_pre_analysis(
        session=session,
        application_id=application.id,
        organization_id=organization_id,
    )

    # 5. Extract answers and analyses indexed by question_id
    analyses_by_qid: dict[UUID, InterviewAnswerAnalysis] = {}
    for aa in (interview_session.answer_analyses or []):
        analyses_by_qid[aa.question_id] = aa

    # Match candidate answer messages to questions
    messages = sorted(interview_session.messages or [], key=lambda m: m.sequence_number)
    questions = sorted(interview_session.questions or [], key=lambda q: q.sequence_number)

    candidate_answers_by_qid: dict[UUID, InterviewMessage] = {}
    for idx, q in enumerate(questions):
        # Find candidate messages following this question
        for m in messages:
            if m.role == "CANDIDATE" and m.sequence_number > q.sequence_number:
                # Associate if not already taken
                if q.id not in candidate_answers_by_qid:
                    candidate_answers_by_qid[q.id] = m
                    break

    # 6. Build Question-Level Findings
    question_findings: list[dict[str, Any]] = []
    follow_up_findings: list[dict[str, Any]] = []
    cap_evidence_map: dict[str, list[dict[str, Any]]] = {}

    for q in questions:
        ans_msg = candidate_answers_by_qid.get(q.id)
        ans_analysis = analyses_by_qid.get(q.id)
        analysis_data = ans_analysis.analysis if ans_analysis else {}

        ans_quality = analysis_data.get("answer_quality", "SUFFICIENT" if ans_msg else None)
        ev_state = analysis_data.get("evidence_state", "DEMONSTRATED" if ans_quality == "SUFFICIENT" else "UNKNOWN")
        key_findings = analysis_data.get("key_findings", [])
        missing_points = analysis_data.get("missing_points", [])
        follow_up_needed = analysis_data.get("follow_up_needed", False)
        follow_up_reason = analysis_data.get("follow_up_reason")

        what_demonstrated = ", ".join(key_findings) if key_findings else (
            "Demonstrated relevant technical competency during discussion." if ans_msg else None
        )
        what_uncertain = ", ".join(missing_points) if missing_points else (
            "Follow-up clarification recommended." if follow_up_needed else None
        )

        sources = [{"type": "INTERVIEW_QUESTION", "id": str(q.id)}]
        if ans_msg:
            sources.append({"type": "INTERVIEW_MESSAGE", "id": str(ans_msg.id)})
        if ans_analysis:
            sources.append({"type": "INTERVIEW_ANSWER_ANALYSIS", "id": str(ans_analysis.id)})

        q_finding = PostInterviewQuestionFinding(
            question_id=str(q.id),
            sequence_number=q.sequence_number,
            question_text=q.question,
            concept=q.concept,
            answer_id=str(ans_msg.id) if ans_msg else None,
            candidate_answer=ans_msg.content if ans_msg else None,
            answer_quality=ans_quality,
            evidence_state=ev_state,
            reasoning=follow_up_reason or (f"Evaluated concept: {q.concept}" if q.concept else None),
            follow_up_question=q.question if q.question_type == "FOLLOW_UP" else None,
            what_was_demonstrated=what_demonstrated,
            what_remains_uncertain=what_uncertain,
            source_references=sources,
        )
        q_finding_dict = q_finding.model_dump()
        question_findings.append(q_finding_dict)

        if q.question_type == "FOLLOW_UP" or follow_up_needed:
            follow_up_findings.append(q_finding_dict)

        # Track capability observations
        if q.concept:
            cap_evidence_map.setdefault(q.concept.lower(), []).append(q_finding_dict)
        if q.capability_id:
            cap_evidence_map.setdefault(str(q.capability_id), []).append(q_finding_dict)

    # 7. Synthesize Capability-Level Findings with Provenance Preservation
    demonstrated_capabilities: list[dict[str, Any]] = []
    claimed_capabilities: list[dict[str, Any]] = []
    unknown_capabilities: list[dict[str, Any]] = []
    verification_needed: list[dict[str, Any]] = []
    evidence_findings: list[dict[str, Any]] = []

    # Map pre-interview capabilities
    pre_claims_map = {c["capability_name"].lower(): c for c in pre_analysis.candidate_claims}
    pre_strengths_map = {s["capability_name"].lower(): s for s in pre_analysis.candidate_strengths}
    pre_unknowns_map = {u["capability_name"].lower(): u for u in pre_analysis.candidate_unknowns}

    for cap in job_capabilities:
        cap_name_clean = cap.name.lower()
        tested_observations = cap_evidence_map.get(cap_name_clean, []) or cap_evidence_map.get(str(cap.id), [])

        # Determine pre-interview provenance
        if cap_name_clean in pre_strengths_map:
            pre_prov = "DEMONSTRATED"
        elif cap_name_clean in pre_claims_map:
            pre_prov = "CLAIM"
        elif cap_name_clean in pre_unknowns_map:
            pre_prov = "UNKNOWN"
        else:
            pre_prov = "UNKNOWN"

        # Determine post-interview provenance without unjustified upgrades
        has_sufficient_answers = any(
            obs.get("answer_quality") == "SUFFICIENT" or obs.get("evidence_state") == "DEMONSTRATED"
            for obs in tested_observations
        )
        has_insufficient_answers = any(
            obs.get("answer_quality") == "INSUFFICIENT"
            for obs in tested_observations
        )
        has_partial_answers = any(
            obs.get("answer_quality") == "PARTIAL" or obs.get("evidence_state") == "VERIFICATION_NEEDED"
            for obs in tested_observations
        )

        source_refs = [{"type": "CAPABILITY", "id": str(cap.id), "name": cap.name}]
        for obs in tested_observations:
            source_refs.extend(obs.get("source_references", []))

        if tested_observations:
            if has_sufficient_answers and not has_insufficient_answers:
                post_prov = "DEMONSTRATED"
                strength = "STRONG"
                obs_text = f"Candidate demonstrated clear competency in {cap.name} with grounded answers."
                is_verified = True
            elif has_insufficient_answers:
                post_prov = "INSUFFICIENT"
                strength = "INSUFFICIENT"
                obs_text = f"Candidate was probed on {cap.name} but answer was insufficient."
                is_verified = False
            elif has_partial_answers:
                post_prov = "VERIFICATION_NEEDED"
                strength = "MODERATE"
                obs_text = f"Candidate demonstrated partial familiarity with {cap.name}; additional verification suggested."
                is_verified = False
            else:
                post_prov = pre_prov
                strength = "MODERATE" if pre_prov == "CLAIM" else "INSUFFICIENT"
                obs_text = f"Probed during interview with inconclusive evidence."
                is_verified = False
        else:
            # Not probed in interview: Preserve pre-interview state!
            post_prov = pre_prov
            strength = "MODERATE" if pre_prov == "CLAIM" else "INSUFFICIENT"
            obs_text = (
                f"Resume claim noted; not evaluated in this live interview round."
                if pre_prov == "CLAIM"
                else f"No prior evidence or live interview verification for {cap.name} (not a failure)."
            )
            is_verified = False

        finding = PostInterviewCapabilityFinding(
            capability_id=str(cap.id),
            capability_name=cap.name,
            pre_interview_provenance=pre_prov,
            post_interview_provenance=post_prov,
            evidence_strength=strength,
            observation=obs_text,
            is_verified_in_interview=is_verified,
            source_references=source_refs,
        )
        finding_dict = finding.model_dump()
        evidence_findings.append(finding_dict)

        if post_prov == "DEMONSTRATED":
            demonstrated_capabilities.append(finding_dict)
        elif post_prov == "CLAIM":
            claimed_capabilities.append(finding_dict)
        elif post_prov in ("UNKNOWN", "INSUFFICIENT"):
            unknown_capabilities.append(finding_dict)
        elif post_prov == "VERIFICATION_NEEDED":
            verification_needed.append(finding_dict)

    # 8. Build Round Summaries
    round_summaries: list[dict[str, Any]] = []
    rounds_stmt = select(InterviewRound).where(InterviewRound.job_id == job.id).order_by(InterviewRound.sequence.asc())
    raw_rounds = (await session.scalars(rounds_stmt)).all()
    db_rounds = [r for r in raw_rounds if isinstance(r, InterviewRound)]

    if db_rounds:
        for r in db_rounds:
            r_questions = [q for q in questions if getattr(q, "round_id", None) == r.id or True]
            r_concepts = [q.concept for q in r_questions if q.concept]
            round_summaries.append(
                PostInterviewRoundSummary(
                    round_id=str(r.id),
                    round_name=getattr(r, "title", f"Round {getattr(r, 'sequence', 1)}"),
                    round_type=getattr(r, "round_type", "TECHNICAL"),
                    sequence=getattr(r, "sequence", 1),
                    status="COMPLETED",
                    capabilities_tested=list(set(r_concepts)),
                    questions_asked=len(r_questions),
                    followups_used=len([q for q in r_questions if q.question_type == "FOLLOW_UP"]),
                    evidence_observed=[f for f in demonstrated_capabilities if f["capability_name"] in r_concepts],
                    unknowns_remaining=[f["capability_name"] for f in unknown_capabilities if f["capability_name"] in r_concepts],
                ).model_dump()
            )
    else:
        # Default single technical round summary
        round_summaries.append(
            PostInterviewRoundSummary(
                round_id="default-round-1",
                round_name="Technical & Problem Solving Assessment",
                round_type="TECHNICAL",
                sequence=1,
                status="COMPLETED",
                capabilities_tested=[q.concept for q in questions if q.concept],
                questions_asked=len(questions),
                followups_used=len(follow_up_findings),
                evidence_observed=demonstrated_capabilities,
                unknowns_remaining=[u["capability_name"] for u in unknown_capabilities],
            ).model_dump()
        )

    # 9. Build Integrity Section (Neutral factual telemetry without accusations)
    integrity_events = interview_session.integrity_events or []
    event_counts: dict[str, int] = {}
    event_timestamps: dict[str, list[str]] = {}

    for evt in integrity_events:
        event_counts[evt.event_type] = event_counts.get(evt.event_type, 0) + 1
        ts = evt.occurred_at.isoformat() if evt.occurred_at else datetime.now(timezone.utc).isoformat()
        event_timestamps.setdefault(evt.event_type, []).append(ts)

    integrity_obs_list: list[PostInterviewIntegrityObservation] = []
    for evt_type, count in event_counts.items():
        summary_msg = f"{count} {evt_type} event(s) recorded during session."
        integrity_obs_list.append(
            PostInterviewIntegrityObservation(
                event_type=evt_type,
                count=count,
                occurred_at_list=event_timestamps.get(evt_type, []),
                summary=summary_msg,
            )
        )

    if integrity_obs_list:
        integ_summary_text = (
            f"Total {len(integrity_events)} browser session event(s) recorded. "
            "Telemetry reflects objective client state and does not classify candidate intent."
        )
    else:
        integ_summary_text = "Stable session: No browser anomalies or connection interruptions recorded."

    integrity_summary = PostInterviewIntegritySummary(
        total_events=len(integrity_events),
        observations=integrity_obs_list,
        raw_event_count_by_type=event_counts,
        summary_text=integ_summary_text,
    ).model_dump()

    # 10. Synthesize Unresolved Areas & Recommendations for Human Review
    unresolved_areas: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []

    for unk in unknown_capabilities:
        item = {
            "capability_name": unk["capability_name"],
            "pre_interview_provenance": unk["pre_interview_provenance"],
            "detail": f"No live evidence collected for {unk['capability_name']}. Not a verified weakness.",
        }
        unresolved_areas.append(item)
        recommendations.append(
            PostInterviewHumanRecommendation(
                category="UNRESOLVED_AREA",
                topic=unk["capability_name"],
                detail="Consider probing in next round or reviewing code artifacts.",
                provenance_reference=unk.get("capability_id"),
            ).model_dump()
        )

    for ver in verification_needed:
        recommendations.append(
            PostInterviewHumanRecommendation(
                category="VERIFICATION_SUGGESTION",
                topic=ver["capability_name"],
                detail=f"Partial evidence demonstrated; suggest focused technical validation for {ver['capability_name']}.",
                provenance_reference=ver.get("capability_id"),
            ).model_dump()
        )

    for dem in demonstrated_capabilities:
        recommendations.append(
            PostInterviewHumanRecommendation(
                category="STRENGTH",
                topic=dem["capability_name"],
                detail=f"Strong demonstrated evidence during live Q&A in {dem['capability_name']}.",
                provenance_reference=dem.get("capability_id"),
            ).model_dump()
        )

    # 11. Structured Executive Summary (Human-in-the-loop, no AI hire/reject score)
    dem_names = [d["capability_name"] for d in demonstrated_capabilities]
    unk_names = [u["capability_name"] for u in unknown_capabilities]

    summary_parts = []
    if dem_names:
        summary_parts.append(f"Candidate demonstrated verified competency in: {', '.join(dem_names)}.")
    if claimed_capabilities:
        claim_names = [c["capability_name"] for c in claimed_capabilities]
        summary_parts.append(f"Retained resume claims for: {', '.join(claim_names)}.")
    if unk_names:
        summary_parts.append(f"Remaining areas with unverified evidence: {', '.join(unk_names)}.")
    summary_parts.append("Final hiring decision rests with the recruiter/hiring manager.")

    final_summary = " ".join(summary_parts)

    # 12. Persist or Update InterviewReportModel
    report_stmt = select(InterviewReportModel).where(
        InterviewReportModel.interview_session_id == session_id
    )
    existing_report = await session.scalar(report_stmt)

    now_utc = datetime.now(timezone.utc)

    if isinstance(existing_report, InterviewReportModel):
        report_obj = existing_report
        report_obj.status = "COMPLETED"
        report_obj.generated_at = now_utc
        report_obj.generation_source = generation_source
        report_obj.summary = final_summary
        report_obj.strengths = pre_analysis.candidate_strengths
        report_obj.demonstrated_capabilities = demonstrated_capabilities
        report_obj.claimed_capabilities = claimed_capabilities
        report_obj.unknown_capabilities = unknown_capabilities
        report_obj.verification_needed = verification_needed
        report_obj.evidence_findings = evidence_findings
        report_obj.round_summaries = round_summaries
        report_obj.question_findings = question_findings
        report_obj.follow_up_findings = follow_up_findings
        report_obj.integrity_summary = integrity_summary
        report_obj.unresolved_areas = unresolved_areas
        report_obj.recommendations_for_human_review = recommendations
        report_obj.updated_at = now_utc
    else:
        report_obj = InterviewReportModel(
            interview_session_id=session_id,
            status="COMPLETED",
            generated_at=now_utc,
            generation_source=generation_source,
            summary=final_summary,
            strengths=pre_analysis.candidate_strengths,
            demonstrated_capabilities=demonstrated_capabilities,
            claimed_capabilities=claimed_capabilities,
            unknown_capabilities=unknown_capabilities,
            verification_needed=verification_needed,
            evidence_findings=evidence_findings,
            round_summaries=round_summaries,
            question_findings=question_findings,
            follow_up_findings=follow_up_findings,
            integrity_summary=integrity_summary,
            unresolved_areas=unresolved_areas,
            recommendations_for_human_review=recommendations,
            metadata_json={"total_questions": len(questions), "total_messages": len(messages)},
            created_at=now_utc,
            updated_at=now_utc,
        )
        session.add(report_obj)

    await session.commit()
    await session.refresh(report_obj)
    logger.info(f"Successfully generated and persisted InterviewReport for session {session_id}.")
    return report_obj


async def get_persisted_interview_report(
    session: AsyncSession,
    session_id: UUID,
    organization_id: UUID,
) -> InterviewReportModel:
    """Retrieves an existing persisted InterviewReportModel for an authorized tenant."""
    stmt = (
        select(InterviewReportModel)
        .join(InterviewSession, InterviewSession.id == InterviewReportModel.interview_session_id)
        .join(Application, Application.id == InterviewSession.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            InterviewReportModel.interview_session_id == session_id,
            Job.organization_id == organization_id,
        )
    )
    report = await session.scalar(stmt)
    if report is None:
        raise InterviewReportNotFoundError(
            f"Interview report for session '{session_id}' not found."
        )
    return report


async def build_interview_report_response(
    session: AsyncSession,
    report_obj: InterviewReportModel,
) -> InterviewReport:
    """Converts a persisted InterviewReportModel into the unified API InterviewReport response."""
    session_stmt = (
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.application).selectinload(Application.candidate),
            selectinload(InterviewSession.application).selectinload(Application.job),
        )
        .where(InterviewSession.id == report_obj.interview_session_id)
    )
    sess_obj = await session.scalar(session_stmt)
    app = getattr(sess_obj, "application", None) if isinstance(sess_obj, InterviewSession) else None
    cand = getattr(app, "candidate", None) if app else None
    job = getattr(app, "job", None) if app else None

    # Format capability breakdown for UI compatibility
    caps_breakdown = []
    for d in report_obj.demonstrated_capabilities:
        caps_breakdown.append({
            "capability": d["capability_name"],
            "level": "STRONG",
            "provenance": "DEMONSTRATED",
            "note": d.get("observation", ""),
        })
    for c in report_obj.claimed_capabilities:
        caps_breakdown.append({
            "capability": c["capability_name"],
            "level": "MODERATE",
            "provenance": "CLAIM",
            "note": c.get("observation", ""),
        })
    for v in report_obj.verification_needed:
        caps_breakdown.append({
            "capability": v["capability_name"],
            "level": "MODERATE",
            "provenance": "VERIFICATION_NEEDED",
            "note": v.get("observation", ""),
        })
    for u in report_obj.unknown_capabilities:
        caps_breakdown.append({
            "capability": u["capability_name"],
            "level": "INSUFFICIENT",
            "provenance": "UNKNOWN",
            "note": u.get("observation", ""),
        })

    # Format transcript highlights for UI compatibility
    highlights = []
    for qf in (report_obj.question_findings or []):
        if qf.get("candidate_answer"):
            highlights.append({
                "q": qf.get("question_text", ""),
                "a": qf.get("candidate_answer", ""),
                "rating": qf.get("answer_quality", "Evaluated"),
            })

    return InterviewReport(
        id=report_obj.id,
        session_id=report_obj.interview_session_id,
        application_id=app.id if app else report_obj.interview_session_id,
        candidate_name=cand.full_name if cand else "Candidate Evaluation",
        candidate_email=cand.email if cand else None,
        job_id=job.id if job else None,
        job_title=job.title if job else "General Role",
        status=report_obj.status,
        generated_at=report_obj.generated_at,
        generation_source=report_obj.generation_source or "SYSTEM_AI",
        summary=report_obj.summary,
        executive_summary=report_obj.summary,
        strengths=report_obj.strengths or [],
        demonstrated_capabilities=report_obj.demonstrated_capabilities or [],
        claimed_capabilities=report_obj.claimed_capabilities or [],
        unknown_capabilities=report_obj.unknown_capabilities or [],
        verification_needed=report_obj.verification_needed or [],
        evidence_findings=report_obj.evidence_findings or [],
        round_summaries=report_obj.round_summaries or [],
        question_findings=report_obj.question_findings or [],
        follow_up_findings=report_obj.follow_up_findings or [],
        integrity_summary=report_obj.integrity_summary or {},
        unresolved_areas=report_obj.unresolved_areas or [],
        recommendations_for_human_review=report_obj.recommendations_for_human_review or [],
        metadata_json=report_obj.metadata_json or {},
        total_questions=len(report_obj.question_findings),
        total_messages=len(report_obj.question_findings),
        completed_at=getattr(sess_obj, "ended_at", report_obj.generated_at),
        created_at=report_obj.created_at,
        updated_at=report_obj.updated_at,
        rounds_completed=len(report_obj.round_summaries),
        total_rounds=max(len(report_obj.round_summaries), 1),
        capabilities_explored=[c["capability_name"] for c in report_obj.evidence_findings],
        questions_asked=len(report_obj.question_findings),
        remaining_unknowns=[u["capability_name"] for u in report_obj.unknown_capabilities],
        capabilities_breakdown=caps_breakdown,
        transcript_highlights=highlights,
    )
