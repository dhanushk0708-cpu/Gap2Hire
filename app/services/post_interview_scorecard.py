from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import inspect

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_scorecard import CandidateScorecard
from app.models.capability import Capability
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_answer_analysis import InterviewAnswerAnalysis
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.post_interview_scorecard import (
    InterviewEvidenceItem,
    PostInterviewCapabilityScorecardItem,
    PostInterviewChangeTypeEnum,
    PostInterviewScorecard,
)
from app.schemas.pre_interview_scorecard import (
    ConfidenceLevelEnum,
    PreInterviewCapabilityStatusEnum,
    PreInterviewScorecard,
    ScorecardEvidenceItem,
    ScorecardVerificationRecommendation,
)
from app.services.application import ApplicationNotFoundError
from app.services.interview import (
    InterviewSessionNotFoundError,
    InvalidSessionStateError,
)
from app.services.pre_interview_scorecard import generate_pre_interview_scorecard

logger = logging.getLogger(__name__)


async def generate_post_interview_scorecard(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    force_refresh: bool = False,
) -> PostInterviewScorecard:
    """
    Constructs an evidence-grounded Post-Interview Analytical Scorecard:
    - Enforces tenant isolation and application validity.
    - Preserves the original pre-interview scorecard as an immutable historical baseline.
    - Evaluates interview questions, answers, answer evaluations, and practical verifications.
    - Maps live observations capability-by-capability with explicit change types and rationales.
    - Honors the core principle: absence of interview questioning is not failure (untested skills remain unknown).
    - Computes progression delta and readiness score without predicting job success or making automated hiring decisions.
    - Persists the post-interview assessment into CandidateScorecard table.
    """
    # 1. Load Application with Candidate, Job, and Tenant validation
    app_stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
    )
    application = await session.scalar(app_stmt)
    if application is None:
        raise ApplicationNotFoundError(f"Application {application_id} not found or inaccessible")

    candidate = application.candidate
    job = application.job

    # 2. Find completed InterviewSession for this application
    sess_stmt = (
        select(InterviewSession)
        .where(InterviewSession.application_id == application_id)
        .order_by(InterviewSession.created_at.desc())
        .options(
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.messages),
            selectinload(InterviewSession.answer_analyses),
        )
    )
    interview_session = await session.scalar(sess_stmt)
    if interview_session is None:
        raise InvalidSessionStateError(f"No interview session found for application {application_id}.")

    if interview_session.status != "COMPLETED":
        raise InvalidSessionStateError(
            f"Cannot generate post-interview scorecard: Interview session status is '{interview_session.status}'. Expected 'COMPLETED'."
        )

    # 3. Check for existing persisted post-interview scorecard (unless force_refresh is requested)
    post_scorecard_stmt = (
        select(CandidateScorecard)
        .where(
            CandidateScorecard.application_id == application_id,
            CandidateScorecard.scorecard_type == "POST_INTERVIEW",
            CandidateScorecard.interview_session_id == interview_session.id,
        )
        .order_by(CandidateScorecard.version.desc())
    )
    existing_post_rec = await session.scalar(post_scorecard_stmt)
    if existing_post_rec is not None and not force_refresh:
        return PostInterviewScorecard.model_validate(existing_post_rec.scorecard_data)

    # 4. Load or Establish Original Pre-Interview Baseline Scorecard
    baseline_stmt = (
        select(CandidateScorecard)
        .where(
            CandidateScorecard.application_id == application_id,
            CandidateScorecard.scorecard_type == "PRE_INTERVIEW",
            CandidateScorecard.is_baseline == True,
        )
        .order_by(CandidateScorecard.version.asc())
    )
    baseline_rec = await session.scalar(baseline_stmt)

    if baseline_rec is None:
        # Generate baseline snapshot for legacy applications
        baseline_scorecard = await generate_pre_interview_scorecard(
            session=session,
            application_id=application_id,
            organization_id=organization_id,
            force_refresh=False,
        )
        baseline_rec = await session.scalar(baseline_stmt)
        if baseline_rec is None:
            # Fallback in-memory baseline ID
            baseline_id = uuid4()
            baseline_ts = baseline_scorecard.assessment_timestamp
        else:
            baseline_id = baseline_rec.id
            baseline_ts = baseline_rec.created_at
    else:
        baseline_scorecard = PreInterviewScorecard.model_validate(baseline_rec.scorecard_data)
        baseline_id = baseline_rec.id
        baseline_ts = baseline_rec.created_at

    # Index baseline items by capability ID and name
    baseline_by_id = {c.capability_id: c for c in baseline_scorecard.capabilities}
    baseline_by_name = {c.capability_name.strip().lower(): c for c in baseline_scorecard.capabilities}

    # 5. Load Job Capabilities
    caps_stmt = (
        select(Capability)
        .where(Capability.job_id == job.id)
        .order_by(Capability.created_at.asc())
    )
    capabilities = list((await session.scalars(caps_stmt)).all())

    # 6. Extract Interview Q&A, Evaluations, and Verifications
    questions = sorted(interview_session.questions or [], key=lambda q: q.sequence_number)
    messages = sorted(interview_session.messages or [], key=lambda m: m.sequence_number)
    analyses_by_qid = {aa.question_id: aa for aa in (interview_session.answer_analyses or [])}

    # Match candidate responses
    candidate_answers_by_qid: dict[UUID, str] = {}
    for q in questions:
        if q.answer:
            candidate_answers_by_qid[q.id] = q.answer
        else:
            # Look up following CANDIDATE message
            for m in messages:
                if m.role == "CANDIDATE" and m.sequence_number > q.sequence_number:
                    candidate_answers_by_qid[q.id] = m.content
                    break

    # Load Verifications
    ver_stmt = select(Verification).where(Verification.application_id == application_id)
    verifications = list((await session.scalars(ver_stmt)).all())
    ver_by_cap = {v.capability_id: v for v in verifications}

    # 7. Capability-by-Capability Comparison
    post_capabilities: list[PostInterviewCapabilityScorecardItem] = []
    supported_count = 0
    partial_count = 0
    unknown_count = 0
    contradictory_count = 0
    strengthened_count = 0
    unverified_count = 0
    critical_needs: list[str] = []

    for cap in capabilities:
        cap_id = cap.id
        cap_name_key = cap.name.strip().lower()

        # Find matching baseline item
        baseline_item = baseline_by_id.get(cap_id) or baseline_by_name.get(cap_name_key)
        if baseline_item is None:
            # Synthesize fallback baseline item if newly added capability
            orig_status = PreInterviewCapabilityStatusEnum.UNKNOWN
            orig_conf = ConfidenceLevelEnum.NONE
            orig_rationale = f"No pre-interview record for {cap.name}."
            orig_ev = []
            orig_guidance = None
        else:
            orig_status = baseline_item.status
            orig_conf = baseline_item.confidence
            orig_rationale = baseline_item.status_rationale
            orig_ev = baseline_item.supporting_evidence
            orig_guidance = baseline_item.recommended_verification.guidance if baseline_item.recommended_verification else None

        # Find interview questions addressing this capability
        matching_questions: list[InterviewQuestion] = []
        for q in questions:
            if q.capability_id == cap_id:
                matching_questions.append(q)
            elif q.concept and (q.concept.strip().lower() == cap_name_key or q.concept.strip().lower() in cap_name_key):
                matching_questions.append(q)

        interview_evidence_items: list[InterviewEvidenceItem] = []
        highest_quality: str | None = None
        has_sufficient_answer = False
        has_partial_answer = False
        has_contradiction = False

        for mq in matching_questions:
            cand_ans = candidate_answers_by_qid.get(mq.id)
            analysis_obj = analyses_by_qid.get(mq.id)
            analysis_dict = analysis_obj.analysis if analysis_obj else {}

            ans_quality = analysis_dict.get("answer_quality")
            if not ans_quality and cand_ans:
                ans_quality = "SUFFICIENT" if len(cand_ans.strip()) > 30 else "PARTIAL"

            key_findings = analysis_dict.get("key_findings", [])
            missing_points = analysis_dict.get("missing_points", [])

            summary_text = (
                ", ".join(key_findings)
                if key_findings
                else ("Candidate articulated clear technical approach during live Q&A." if cand_ans else "No answer recorded.")
            )

            # Check for contradiction flags
            if analysis_dict.get("is_contradictory") or "contradict" in summary_text.lower():
                has_contradiction = True

            if ans_quality == "SUFFICIENT":
                has_sufficient_answer = True
                highest_quality = "SUFFICIENT"
            elif ans_quality == "PARTIAL":
                has_partial_answer = True
                if highest_quality != "SUFFICIENT":
                    highest_quality = "PARTIAL"

            limitations_note = (
                ", ".join(missing_points)
                if missing_points
                else ("Evaluated via live conversational Q&A without automated unit test execution." if cand_ans else "Question not answered.")
            )

            interview_evidence_items.append(
                InterviewEvidenceItem(
                    session_id=str(interview_session.id),
                    question_id=str(mq.id),
                    question_text=mq.question,
                    candidate_answer_excerpt=cand_ans[:280] + "..." if cand_ans and len(cand_ans) > 280 else cand_ans,
                    evaluation_summary=summary_text,
                    evaluation_quality=ans_quality or "UNANSWERED",
                    source_timestamp=mq.created_at.isoformat() if mq.created_at else None,
                    limitations=limitations_note,
                )
            )

        # Check post-interview verifications
        ver = ver_by_cap.get(cap_id)
        has_passed_verification = ver is not None and ver.result == "PASS"

        # Determine Updated Status, Confidence, and Change Analysis
        if has_contradiction:
            updated_status = PreInterviewCapabilityStatusEnum.CONTRADICTORY
            updated_conf = ConfidenceLevelEnum.MEDIUM
            change_type = PostInterviewChangeTypeEnum.CONTRADICTORY
            change_summary = (
                f"Candidate provided responses during the interview that conflicted with earlier resume/portfolio claims "
                f"regarding {cap.name}. Direct human recruiter review is required."
            )
            updated_rationale = f"Contradictory evidence detected during live technical questioning on {cap.name}."
            contradictory_count += 1
            if cap.importance in ("CRITICAL", "HIGH"):
                critical_needs.append(f"{cap.name} (Conflicting Interview Evidence)")

            rec_followup = ScorecardVerificationRecommendation(
                action_type="HUMAN_AUDIT",
                priority="HIGH",
                guidance=f"Conduct debrief with candidate to resolve discrepancies in {cap.name}.",
            )
            rem_uncertainties = "Ambiguity between self-reported experience and live statements."

        elif has_passed_verification or (has_sufficient_answer and orig_status in (PreInterviewCapabilityStatusEnum.UNKNOWN, PreInterviewCapabilityStatusEnum.PARTIAL)):
            updated_status = PreInterviewCapabilityStatusEnum.SUPPORTED
            updated_conf = ConfidenceLevelEnum.HIGH if (has_passed_verification or len(matching_questions) >= 2) else ConfidenceLevelEnum.MEDIUM
            change_type = PostInterviewChangeTypeEnum.STRENGTHENED
            strengthened_count += 1
            supported_count += 1
            change_summary = (
                f"Status upgraded from {orig_status.value} to SUPPORTED. The candidate provided detailed, technically sound "
                f"answers during the interview, demonstrating verified competence in {cap.name}."
            )
            updated_rationale = f"Capability demonstrated and verified during live interview questioning on {cap.name}."
            rec_followup = ScorecardVerificationRecommendation(
                action_type="TECHNICAL_CONFIRMATION",
                priority="LOW",
                guidance=f"Evidence verified during interview; no further technical validation required for {cap.name}.",
            )
            rem_uncertainties = None

        elif orig_status == PreInterviewCapabilityStatusEnum.SUPPORTED and (has_sufficient_answer or len(matching_questions) == 0):
            updated_status = PreInterviewCapabilityStatusEnum.SUPPORTED
            updated_conf = ConfidenceLevelEnum.HIGH
            change_type = PostInterviewChangeTypeEnum.CONFIRMED
            supported_count += 1
            change_summary = (
                f"Baseline SUPPORTED status was confirmed. Pre-interview evidence remains solid and consistent "
                f"with interview observations for {cap.name}."
            )
            updated_rationale = f"Pre-interview verified competency in {cap.name} reaffirmed post-interview."
            rec_followup = ScorecardVerificationRecommendation(
                action_type="TECHNICAL_CONFIRMATION",
                priority="LOW",
                guidance="Capability verified.",
            )
            rem_uncertainties = None

        elif has_partial_answer or (orig_status == PreInterviewCapabilityStatusEnum.PARTIAL and len(matching_questions) == 0):
            updated_status = PreInterviewCapabilityStatusEnum.PARTIAL
            updated_conf = ConfidenceLevelEnum.LOW
            change_type = PostInterviewChangeTypeEnum.UNVERIFIED_CLAIM
            partial_count += 1
            unverified_count += 1
            change_summary = (
                f"Capability remains PARTIAL. The candidate provided basic conceptual explanations for {cap.name}, "
                f"but answers lacked detailed architectural depth or practical production examples."
            )
            updated_rationale = f"Live responses provided conceptual exposure but did not establish verified mastery in {cap.name}."
            rec_followup = ScorecardVerificationRecommendation(
                action_type="INTERVIEW_PROBE",
                priority="HIGH" if cap.importance in ("CRITICAL", "HIGH") else "MEDIUM",
                guidance=f"Request a focused practical code submission or follow-up technical assessment in {cap.name}.",
            )
            rem_uncertainties = "Depth of practical hands-on experience remains unverified."
            if cap.importance in ("CRITICAL", "HIGH"):
                critical_needs.append(f"{cap.name} (Unverified Depth)")

        else:
            # No interview questions asked for this capability -> strictly preserved as UNKNOWN or original baseline
            updated_status = orig_status
            updated_conf = orig_conf
            change_type = PostInterviewChangeTypeEnum.REMAINED_UNKNOWN
            unknown_count += 1
            unverified_count += 1
            change_summary = (
                f"This capability was not tested during this interview session. Absence of interview questioning "
                f"is not candidate failure; competence in {cap.name} remains unknown."
            )
            updated_rationale = (
                f"No live Q&A was conducted for {cap.name}. Preserved original assessment status without penalty."
            )
            rec_followup = ScorecardVerificationRecommendation(
                action_type="EXPLORATORY_PROBE",
                priority="MEDIUM",
                guidance=f"Explore {cap.name} in next interview round or via take-home assignment if required.",
            )
            rem_uncertainties = "No live evidence collected during interview."
            if cap.importance in ("CRITICAL", "HIGH"):
                critical_needs.append(f"{cap.name} (Untested Capability)")

        post_capabilities.append(
            PostInterviewCapabilityScorecardItem(
                capability_id=cap_id,
                capability_name=cap.name,
                requirement_description=cap.description,
                importance=cap.importance,
                original_status=orig_status,
                original_confidence=orig_conf,
                original_rationale=orig_rationale,
                original_evidence=orig_ev,
                original_verification_guidance=orig_guidance,
                updated_status=updated_status,
                updated_confidence=updated_conf,
                updated_rationale=updated_rationale,
                interview_evidence=interview_evidence_items,
                remaining_uncertainties=rem_uncertainties,
                recommended_follow_up=rec_followup,
                change_type=change_type,
                change_summary=change_summary,
            )
        )

    # 8. Compute Aggregate Readiness Score & Deltas
    total_caps = len(capabilities)
    if total_caps > 0:
        post_readiness = round(((supported_count * 1.0) + (partial_count * 0.5)) / total_caps * 100, 1)
    else:
        post_readiness = 0.0

    baseline_readiness = baseline_scorecard.evidence_readiness_score
    delta = round(post_readiness - baseline_readiness, 1)

    score_expl = (
        f"Post-Interview Evidence Readiness measures the completeness of verified evidence after the interview. "
        f"Baseline readiness was {baseline_readiness}%, and post-interview readiness is {post_readiness}% "
        f"(change: {delta:+.1f}%). This score measures evidence completeness across job requirements, "
        f"not candidate worth or probability of job success."
    )

    # Build Executive Summary
    summary_parts = [
        f"Interview evaluation completed for {candidate.full_name} for the position of {job.title}."
    ]
    if strengthened_count > 0:
        summary_parts.append(f"{strengthened_count} capability/capabilities were strengthened with verified live interview evidence.")
    if unverified_count > 0:
        summary_parts.append(f"{unverified_count} requirement(s) remain unverified or were not tested during this session.")
    if contradictory_count > 0:
        summary_parts.append(f"{contradictory_count} requirement(s) displayed conflicting evidence requiring recruiter audit.")
    summary_parts.append("Human recruiter and hiring manager review is required before taking final hiring decisions.")

    exec_summary = " ".join(summary_parts)

    human_notice = (
        "NOTICE FOR EVALUATORS: This post-interview analytical scorecard compares live interview evidence "
        "against the original pre-interview baseline. Untested capabilities remain unknown and are never penalized "
        "as candidate failures. AI assists HR; all shortlisting and hiring decisions require human evaluation."
    )

    now_utc = datetime.now(timezone.utc)
    new_version = (existing_post_rec.version + 1) if existing_post_rec else 1

    post_scorecard = PostInterviewScorecard(
        application_id=application_id,
        job_id=job.id,
        job_title=job.title,
        candidate_id=candidate.id,
        candidate_name=candidate.full_name,
        interview_session_id=interview_session.id,
        assessment_timestamp=now_utc,
        scorecard_version=new_version,
        baseline_scorecard_id=baseline_id,
        baseline_assessment_timestamp=baseline_ts,
        baseline_readiness_score=baseline_readiness,
        post_interview_readiness_score=post_readiness,
        readiness_change_delta=delta,
        score_explanation=score_expl,
        executive_summary=exec_summary,
        total_capabilities=total_caps,
        supported_count=supported_count,
        partial_count=partial_count,
        unknown_count=unknown_count,
        contradictory_count=contradictory_count,
        capabilities_strengthened_count=strengthened_count,
        capabilities_unverified_count=unverified_count,
        critical_verification_needs=critical_needs,
        human_review_notice=human_notice,
        capabilities=post_capabilities,
    )

    # 9. Persist into CandidateScorecard table
    try:
        new_post_rec = CandidateScorecard(
            id=uuid4(),
            application_id=application_id,
            job_id=job.id,
            scorecard_type="POST_INTERVIEW",
            version=new_version,
            is_baseline=False,
            interview_session_id=interview_session.id,
            scorecard_data=post_scorecard.model_dump(mode="json"),
        )
        # Support both sync and async add (e.g., when mocked with AsyncMock)
        add_result = session.add(new_post_rec)
        if inspect.isawaitable(add_result):
            await add_result
        await session.commit()
    except Exception as db_err:
        logger.debug(f"Could not persist post-interview scorecard to CandidateScorecard: {db_err}")

    return post_scorecard
