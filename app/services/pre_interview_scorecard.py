from datetime import datetime
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import inspect

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_scorecard import CandidateScorecard
from app.models.candidate_source import CandidateSource
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewSession
from app.models.interview_dataset import (
    InterviewDatasetFile,
    InterviewDatasetQuestion,
    InterviewQuestionDataset,
)
from app.models.interview_plan import InterviewPlan, InterviewPlanRound
from app.models.interview_round import InterviewQuestionTemplate, InterviewRound
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.pre_interview_scorecard import (
    CapabilityScorecardItem,
    ConfidenceLevelEnum,
    PreInterviewCapabilityStatusEnum,
    PreInterviewScorecard,
    ScorecardEvidenceItem,
    ScorecardVerificationRecommendation,
    TargetedInterviewQuestion,
)
from app.services.application import ApplicationNotFoundError

logger = logging.getLogger(__name__)


def generate_targeted_question(
    cap_name: str,
    cap_desc: str | None,
    status: PreInterviewCapabilityStatusEnum,
    importance: str,
) -> TargetedInterviewQuestion:
    """
    Constructs a practical, role-relevant targeted verification question
    tailored to the capability and gap state.
    """
    clean_desc = (cap_desc or cap_name).strip()

    if status == PreInterviewCapabilityStatusEnum.PARTIAL:
        question_text = (
            f"You mentioned experience with {cap_name} on your resume. Could you describe a specific "
            f"production project where you implemented {clean_desc}, including the trade-offs and challenges you faced?"
        )
        intent = "VERIFY_CLAIM"
        expected_signals = (
            f"Concrete architectural details, hands-on debugging experience, and clear explanation of "
            f"how {cap_name} was applied in production."
        )
    elif status == PreInterviewCapabilityStatusEnum.UNKNOWN:
        question_text = (
            f"While your submission does not explicitly document {cap_name}, our team works heavily with it. "
            f"What exposure or related conceptual experience do you have with {clean_desc}, and how would you approach it here?"
        )
        intent = "PROBE_UNKNOWN"
        expected_signals = (
            f"Foundational problem-solving mindset, fast learning capacity, and understanding of core principles behind {cap_name}."
        )
    elif status == PreInterviewCapabilityStatusEnum.CONTRADICTORY:
        question_text = (
            f"Could you clarify your exact role, timeline, and degree of ownership regarding {cap_name} "
            f"to help us resolve conflicting references in your portfolio/resume?"
        )
        intent = "RESOLVE_CONTRADICTION"
        expected_signals = "Transparent explanation of timeline, individual contributions vs team accomplishments."
    else:  # SUPPORTED
        question_text = (
            f"Given your demonstrated work in {cap_name}, how would you approach scaling and failure recovery "
            f"for {clean_desc} in high-throughput enterprise environments?"
        )
        intent = "DEPTH_VALIDATION"
        expected_signals = "Advanced architectural mastery, failure handling, and operational maturity."

    difficulty = "SENIOR" if importance in ("CRITICAL", "HIGH") else "MID"

    return TargetedInterviewQuestion(
        question_text=question_text,
        intent=intent,
        difficulty=difficulty,
        expected_signals=expected_signals,
        source="Analytical Verification Engine",
    )


async def generate_pre_interview_scorecard(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    force_refresh: bool = False,
) -> PreInterviewScorecard:
    """
    Builds a rigorous, evidence-grounded Pre-Interview Analytical Scorecard for a candidate application:
    - Enforces tenant isolation and application validity.
    - Grounded strictly in persisted Job capabilities, Candidate sources, Evidence, and Verifications.
    - Honors the core principle: Absence of evidence is not evidence of absence (missing skills are UNKNOWN, not FAIL).
    - Transparently justifies confidence and maps targeted verification questions to each gap.
    - Computes an Evidence Readiness Score strictly as an evidence completeness measure.
    - Automatically persists and retrieves the original baseline to guarantee historical immutability.
    """
    # 1. Load Application with Candidate, Job, and CandidateSources (Tenant-scoped)
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
            selectinload(Application.sources),
        )
    )
    application = await session.scalar(app_stmt)
    if application is None:
        raise ApplicationNotFoundError(f"Application {application_id} not found or inaccessible")

    # 1b. Check for existing persisted baseline scorecard
    scorecard_stmt = (
        select(CandidateScorecard)
        .where(
            CandidateScorecard.application_id == application_id,
            CandidateScorecard.scorecard_type == "PRE_INTERVIEW",
        )
        .order_by(CandidateScorecard.version.desc())
    )
    existing_scorecard_rec = await session.scalar(scorecard_stmt)

    if existing_scorecard_rec is not None and not force_refresh:
        return PreInterviewScorecard.model_validate(existing_scorecard_rec.scorecard_data)

    if existing_scorecard_rec is not None and force_refresh:
        # Check if an interview has already started or completed
        has_interview = application.status in ("INTERVIEW", "INTERVIEW_COMPLETED", "HIRED", "REJECTED")
        if not has_interview:
            session_check = await session.scalar(
                select(InterviewSession.id).where(InterviewSession.application_id == application_id)
            )
            has_interview = session_check is not None

        if has_interview:
            logger.info(
                f"Application {application_id} has entered interview lifecycle; "
                "preserving original pre-interview baseline immutable without modification."
            )
            return PreInterviewScorecard.model_validate(existing_scorecard_rec.scorecard_data)

    candidate = application.candidate
    job = application.job

    # 2. Load Job Capabilities
    caps_stmt = (
        select(Capability)
        .where(Capability.job_id == job.id)
        .order_by(Capability.created_at.asc())
    )
    capabilities = list((await session.scalars(caps_stmt)).all())

    # 3. Load Application Evidence
    ev_stmt = select(Evidence).where(Evidence.application_id == application_id)
    evidences = list((await session.scalars(ev_stmt)).all())
    ev_by_cap: dict[UUID, list[Evidence]] = {}
    for ev in evidences:
        ev_by_cap.setdefault(ev.capability_id, []).append(ev)

    # 4. Load Application Verifications
    ver_stmt = select(Verification).where(Verification.application_id == application_id)
    verifications = list((await session.scalars(ver_stmt)).all())
    ver_by_cap = {v.capability_id: v for v in verifications}

    # 5. Load Candidate Sources map
    sources_map = {s.id: s for s in (application.sources or [])}

    # 6. Load Latest Interview Plan if present (to link versioning and plan questions)
    plan_stmt = (
        select(InterviewPlan)
        .where(
            InterviewPlan.application_id == application_id,
            InterviewPlan.organization_id == organization_id,
        )
        .order_by(InterviewPlan.version.desc())
        .options(
            selectinload(InterviewPlan.rounds).selectinload(InterviewPlanRound.questions),
        )
    )
    latest_plan = await session.scalar(plan_stmt)
    scorecard_version = latest_plan.version if latest_plan else 1

    # Load Question bank from datasets for this job/organization
    questions_bank_by_concept: dict[str, list[str]] = {}
    ds_file_stmt = (
        select(InterviewDatasetFile)
        .where(
            InterviewDatasetFile.organization_id == organization_id,
            (InterviewDatasetFile.job_id == job.id) | (InterviewDatasetFile.job_id.is_(None)),
        )
        .order_by(InterviewDatasetFile.created_at.desc())
    )
    dataset_file = await session.scalar(ds_file_stmt)
    if dataset_file:
        q_bank_stmt = (
            select(InterviewDatasetQuestion)
            .join(InterviewQuestionDataset, InterviewQuestionDataset.id == InterviewDatasetQuestion.dataset_id)
            .where(InterviewQuestionDataset.file_id == dataset_file.id)
        )
        all_ds_qs = list((await session.scalars(q_bank_stmt)).all())
        for q in all_ds_qs:
            concept_key = q.concept.strip().lower()
            questions_bank_by_concept.setdefault(concept_key, []).append(q.question_text)

    # 7. Evaluate Capability-by-Capability
    capability_items: list[CapabilityScorecardItem] = []
    supported_count = 0
    partial_count = 0
    unknown_count = 0
    contradictory_count = 0
    critical_needs: list[str] = []

    for cap in capabilities:
        cap_id = cap.id
        cap_evs = ev_by_cap.get(cap_id, [])
        ver = ver_by_cap.get(cap_id)

        # Check for contradictory evidence
        contradictory_ev = next((e for e in cap_evs if e.provenance == "CONTRADICTORY"), None)

        # Check for verified assessment
        has_passed_verification = ver is not None and ver.result == "PASS"

        # Check for demonstrated / corroborated evidence
        demonstrated_ev = next(
            (e for e in cap_evs if e.provenance in ("DEMONSTRATED", "CORROBORATED") and e.strength in ("STRONG", "MODERATE")),
            None,
        )

        # Check for resume claim
        claim_ev = next(
            (e for e in cap_evs if e.provenance == "CLAIM"),
            None,
        )

        supporting_evidence_items: list[ScorecardEvidenceItem] = []

        # Determine Assessment Status & Confidence
        if contradictory_ev is not None:
            status = PreInterviewCapabilityStatusEnum.CONTRADICTORY
            confidence = ConfidenceLevelEnum.MEDIUM
            confidence_justification = (
                "Conflicting evidence discovered across submitted materials and verification records. "
                "Confidence is calibrated to reflect ambiguity requiring human auditor review."
            )
            status_rationale = (
                f"Conflicting claims or timestamps detected regarding {cap.name}. "
                f"Candidate claims require manual review during interview."
            )
            contradictory_count += 1
            if cap.importance in ("CRITICAL", "HIGH"):
                critical_needs.append(f"{cap.name} (Conflicting Evidence)")

            rec_action = ScorecardVerificationRecommendation(
                action_type="HUMAN_AUDIT",
                priority="HIGH",
                guidance=f"Directly ask candidate to clarify timeline and specific ownership regarding {cap.name}.",
            )

        elif has_passed_verification:
            status = PreInterviewCapabilityStatusEnum.SUPPORTED
            confidence = ConfidenceLevelEnum.HIGH
            confidence_justification = (
                f"High confidence: Capability directly verified through passed practical assessment "
                f"({ver.type}) with result {ver.result}."
            )
            status_rationale = f"Candidate independently verified in hands-on assessment for {cap.name}."
            supported_count += 1

            supporting_evidence_items.append(
                ScorecardEvidenceItem(
                    id=str(ver.id),
                    source_type="PRACTICAL_ASSESSMENT",
                    source_reference=f"Assessment: {ver.type}",
                    excerpt=ver.submission_content or f"Passed {ver.type} evaluation.",
                    source_location="Assessment Submissions",
                    provenance="VERIFIED",
                    strength="STRONG",
                    created_at=ver.created_at.isoformat() if ver.created_at else None,
                    limitations="Practical assessment evaluated target capability at time of test.",
                )
            )

            rec_action = ScorecardVerificationRecommendation(
                action_type="TECHNICAL_CONFIRMATION",
                priority="LOW",
                guidance=f"Briefly confirm architectural decisions from practical exercise during technical interview.",
            )

        elif demonstrated_ev is not None:
            status = PreInterviewCapabilityStatusEnum.SUPPORTED
            confidence = ConfidenceLevelEnum.HIGH if demonstrated_ev.strength == "STRONG" else ConfidenceLevelEnum.MEDIUM
            src_obj = sources_map.get(demonstrated_ev.candidate_source_id) if demonstrated_ev.candidate_source_id else None
            src_url = src_obj.url if src_obj else None
            confidence_justification = (
                f"Grounded confidence: Demonstrated with concrete implementation artifacts in candidate sources "
                f"({demonstrated_ev.source_type})."
            )
            status_rationale = f"Concrete demonstration of {cap.name} identified in candidate source artifacts."
            supported_count += 1

            rec_action = ScorecardVerificationRecommendation(
                action_type="CODE_WALKTHROUGH",
                priority="LOW",
                guidance=f"Invite candidate to walk through implementation details of {cap.name} project artifacts.",
            )

        elif claim_ev is not None:
            status = PreInterviewCapabilityStatusEnum.PARTIAL
            confidence = ConfidenceLevelEnum.LOW
            confidence_justification = (
                "Low confidence: Self-reported claim in resume without independent external verification or code artifacts. "
                "Claim must be validated in live interview."
            )
            status_rationale = f"{cap.name} is claimed on resume, but lacks independent external evidence."
            partial_count += 1
            if cap.importance in ("CRITICAL", "HIGH"):
                critical_needs.append(f"{cap.name} (Unverified Resume Claim)")

            rec_action = ScorecardVerificationRecommendation(
                action_type="INTERVIEW_PROBE",
                priority="HIGH" if cap.importance in ("CRITICAL", "HIGH") else "MEDIUM",
                guidance=f"Probe depth of {cap.name} using realistic technical scenario questions.",
            )

        else:
            status = PreInterviewCapabilityStatusEnum.UNKNOWN
            confidence = ConfidenceLevelEnum.NONE
            confidence_justification = (
                "No confidence: Zero evidence discovered in submitted artifacts. "
                "Absence of evidence is not evidence of absence; uncertainty must be explored in interview."
            )
            status_rationale = (
                f"No explicit mention or evidence found for {cap.name}. "
                f"Absence of evidence is not evidence of absence; this does not imply a lack of competence."
            )
            unknown_count += 1
            if cap.importance in ("CRITICAL", "HIGH"):
                critical_needs.append(f"{cap.name} (Unknown - Missing Evidence)")

            rec_action = ScorecardVerificationRecommendation(
                action_type="EXPLORATORY_PROBE",
                priority="HIGH" if cap.importance in ("CRITICAL", "HIGH") else "MEDIUM",
                guidance=f"Ask exploratory questions to assess whether candidate possesses unstated knowledge in {cap.name}.",
            )

        # Populate supporting evidence items from Evidence table
        for ev in cap_evs:
            src_obj = sources_map.get(ev.candidate_source_id) if ev.candidate_source_id else None
            src_ref = src_obj.url if src_obj else (f"Resume File: {application.resume_path}" if application.resume_path else "Resume Document")
            loc_label = src_obj.title if (src_obj and src_obj.title) else "Resume Document"

            supporting_evidence_items.append(
                ScorecardEvidenceItem(
                    id=str(ev.id),
                    source_type=ev.source_type,
                    source_reference=src_ref,
                    excerpt=ev.content or f"Claim regarding {cap.name}",
                    source_location=loc_label,
                    provenance=ev.provenance,
                    strength=ev.strength,
                    created_at=ev.created_at.isoformat() if ev.created_at else None,
                    limitations="Self-reported claim on resume" if ev.provenance == "CLAIM" else "Artifact discovered via automated intake",
                )
            )

        # Assemble Targeted Questions for capability
        targeted_questions: list[TargetedInterviewQuestion] = []

        # 1. Check if dataset question bank has questions for this capability concept
        cap_concept_key = cap.name.strip().lower()
        bank_matches = questions_bank_by_concept.get(cap_concept_key, [])
        for q_text in bank_matches[:2]:
            targeted_questions.append(
                TargetedInterviewQuestion(
                    question_text=q_text,
                    intent="VERIFY_CLAIM" if status == PreInterviewCapabilityStatusEnum.PARTIAL else "PROBE_UNKNOWN",
                    difficulty="SENIOR" if cap.importance in ("CRITICAL", "HIGH") else "MID",
                    expected_signals=f"In-depth grasp of {cap.name} concepts and architectural trade-offs.",
                    source="Interview Dataset Bank",
                )
            )

        # 2. Check if latest interview plan has planned questions for this capability
        if latest_plan and not targeted_questions:
            for rnd in latest_plan.rounds:
                for q in rnd.questions:
                    if q.concept.strip().lower() == cap_concept_key:
                        targeted_questions.append(
                            TargetedInterviewQuestion(
                                question_text=q.question_text,
                                intent="VERIFY_CLAIM" if status == PreInterviewCapabilityStatusEnum.PARTIAL else "PROBE_UNKNOWN",
                                difficulty=q.difficulty or "MEDIUM",
                                expected_signals=q.evidence_being_verified or f"Demonstration of {cap.name} competence.",
                                source=f"Interview Plan (Round {rnd.round_number})",
                            )
                        )

        # 3. Always ensure at least one practical, tailored question exists
        if not targeted_questions:
            targeted_questions.append(
                generate_targeted_question(
                    cap_name=cap.name,
                    cap_desc=cap.description,
                    status=status,
                    importance=cap.importance,
                )
            )

        capability_items.append(
            CapabilityScorecardItem(
                capability_id=str(cap.id),
                capability_name=cap.name,
                requirement_description=cap.description,
                importance=cap.importance,
                status=status,
                status_rationale=status_rationale,
                confidence=confidence,
                confidence_justification=confidence_justification,
                supporting_evidence=supporting_evidence_items,
                recommended_verification=rec_action,
                targeted_questions=targeted_questions,
            )
        )

    # 8. Compute Evidence Readiness Score
    total_caps = len(capabilities)
    if total_caps > 0:
        readiness_score = round(((supported_count * 1.0) + (partial_count * 0.5)) / total_caps * 100, 1)
    else:
        readiness_score = 0.0

    # 9. Build Coherent Executive Summary
    summary_parts = []
    if supported_count > 0:
        summary_parts.append(f"{supported_count} of {total_caps} requirements have verified or demonstrated evidence.")
    if partial_count > 0:
        summary_parts.append(f"{partial_count} requirements are self-reported claims requiring interview verification.")
    if unknown_count > 0:
        summary_parts.append(
            f"{unknown_count} requirements lack documented evidence in submitted artifacts and should be explored during interview."
        )
    if contradictory_count > 0:
        summary_parts.append(f"{contradictory_count} requirement(s) display conflicting data requiring recruiter review.")

    exec_summary = " ".join(summary_parts) if summary_parts else "No capabilities evaluated."

    scorecard = PreInterviewScorecard(
        application_id=application_id,
        job_id=job.id,
        job_title=job.title,
        job_description=job.description,
        candidate_id=candidate.id,
        candidate_name=candidate.full_name,
        candidate_email=candidate.email,
        generated_at=datetime.utcnow(),
        version=scorecard_version,
        capabilities=capability_items,
        total_capabilities=total_caps,
        supported_count=supported_count,
        partial_count=partial_count,
        unknown_count=unknown_count,
        contradictory_count=contradictory_count,
        critical_verification_needs=critical_needs,
        evidence_readiness_score=readiness_score,
        executive_summary=exec_summary,
    )

    # 10. Persist scorecard to CandidateScorecard table and update application audit note
    try:
        new_version = (existing_scorecard_rec.version + 1) if existing_scorecard_rec else 1
        is_baseline = existing_scorecard_rec is None
        scorecard_rec = CandidateScorecard(
            id=uuid4(),
            application_id=application_id,
            job_id=job.id,
            scorecard_type="PRE_INTERVIEW",
            version=new_version,
            is_baseline=is_baseline,
            scorecard_data=scorecard.model_dump(mode="json"),
        )
        # Support both sync and async add (e.g., when mocked with AsyncMock)
        add_result = session.add(scorecard_rec)
        if inspect.isawaitable(add_result):
            await add_result
        application.screening_notes = f"[SCORECARD v{new_version}] {exec_summary} Readiness: {readiness_score}%"
        await session.commit()
    except Exception as db_err:
        logger.debug(f"Could not persist scorecard to CandidateScorecard table: {db_err}")

    return scorecard
