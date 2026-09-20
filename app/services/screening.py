from datetime import datetime
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.screening import (
    CandidateScreeningResult,
    JobCandidateListItem,
    RequirementEvaluation,
    ShortlistDecisionResponse,
)

logger = logging.getLogger(__name__)


class ApplicationNotFoundError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class InvalidShortlistDecisionError(Exception):
    pass


class CandidateNotShortlistedError(Exception):
    pass


VALID_SHORTLIST_DECISIONS = {"SHORTLISTED", "NOT_SHORTLISTED", "HOLD"}


async def evaluate_candidate_eligibility(
    job: Job,
    application: Application,
    capabilities: list[Capability],
    evidence_list: list[Evidence],
    verifications: list[Verification] | None = None,
) -> tuple[str, list[RequirementEvaluation]]:
    """Evaluates candidate eligibility against job capabilities and requirements."""
    evaluations: list[RequirementEvaluation] = []
    verifs = verifications or []
    verif_map = {v.capability_id: v for v in verifs if v.result == "PASS"}
    ev_map: dict[UUID, list[Evidence]] = {}
    for ev in evidence_list:
        ev_map.setdefault(ev.capability_id, []).append(ev)

    met_count = 0
    unknown_count = 0

    for cap in capabilities:
        cap_id = cap.id
        cap_evs = ev_map.get(cap_id, [])
        is_verified = cap_id in verif_map

        if is_verified:
            evaluations.append(
                RequirementEvaluation(
                    requirement_name=cap.name,
                    requirement_type="CAPABILITY",
                    status="MET",
                    evidence_found="Practical verification passed.",
                    provenance="VERIFIED",
                    strength="STRONG",
                    reason=f"Candidate successfully passed practical exercise for {cap.name}.",
                )
            )
            met_count += 1
        elif cap_evs:
            # Resume evidence is strictly CLAIM
            primary_ev = cap_evs[0]
            strength = primary_ev.strength or "STRONG"
            evaluations.append(
                RequirementEvaluation(
                    requirement_name=cap.name,
                    requirement_type="CAPABILITY",
                    status="MET" if strength in {"STRONG", "MODERATE"} else "NEEDS_REVIEW",
                    evidence_found=primary_ev.content,
                    provenance="CLAIM",
                    strength=strength,
                    reason=f"Resume claim identified for {cap.name} (Provenance: CLAIM, Strength: {strength}).",
                )
            )
            if strength in {"STRONG", "MODERATE"}:
                met_count += 1
            else:
                unknown_count += 1
        else:
            evaluations.append(
                RequirementEvaluation(
                    requirement_name=cap.name,
                    requirement_type="CAPABILITY",
                    status="UNKNOWN",
                    evidence_found=None,
                    provenance="UNKNOWN",
                    strength=None,
                    reason=f"No explicit mention or evidence found in resume for {cap.name}. Marked for evaluation.",
                )
            )
            unknown_count += 1

    # Overall eligibility logic: never fail unknown automatically
    if not capabilities:
        eligibility = "ELIGIBLE" if application.resume_text else "NEEDS_REVIEW"
    elif met_count == len(capabilities):
        eligibility = "ELIGIBLE"
    elif met_count > 0 and unknown_count > 0:
        eligibility = "NEEDS_REVIEW"
    elif met_count == 0 and unknown_count > 0:
        eligibility = "NEEDS_REVIEW"
    else:
        eligibility = "NOT_ELIGIBLE"

    return eligibility, evaluations


async def build_candidate_screening_report(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> CandidateScreeningResult:
    """Generates structured screening analysis explaining requirements considered, evidence available, and unknowns."""
    stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
        .options(selectinload(Application.candidate), selectinload(Application.job))
    )
    application = await session.scalar(stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found or inaccessible")

    job = application.job
    candidate = application.candidate

    # Load capabilities
    caps_stmt = select(Capability).where(Capability.job_id == job.id).order_by(Capability.created_at.asc())
    capabilities = list((await session.scalars(caps_stmt)).all())

    # Load evidence
    ev_stmt = select(Evidence).where(Evidence.application_id == application_id)
    evidence_list = list((await session.scalars(ev_stmt)).all())

    # Load verifications
    ver_stmt = select(Verification).where(Verification.application_id == application_id)
    verifications = list((await session.scalars(ver_stmt)).all())

    # Evaluate eligibility
    eligibility_status, evaluations = await evaluate_candidate_eligibility(
        job=job,
        application=application,
        capabilities=capabilities,
        evidence_list=evidence_list,
        verifications=verifications,
    )

    claims_summary: list[str] = []
    unknowns_summary: list[str] = []
    missing_info: list[str] = []

    for ev in evaluations:
        if ev.status == "MET" and ev.provenance == "CLAIM":
            claims_summary.append(f"{ev.requirement_name}: {ev.evidence_found} (Claim)")
        elif ev.status in {"UNKNOWN", "NEEDS_REVIEW"}:
            unknowns_summary.append(ev.requirement_name)
            missing_info.append(f"Verification needed for {ev.requirement_name}")

    # Build human-readable summary explanation
    total_reqs = len(evaluations)
    met_reqs = len([e for e in evaluations if e.status == "MET"])
    explanation = (
        f"Screening evaluation for {candidate.full_name} against {job.title}: "
        f"{met_reqs}/{total_reqs} capability claims identified from resume. "
    )
    if unknowns_summary:
        explanation += f"Unknown areas needing interview probing: {', '.join(unknowns_summary)}. "
    if eligibility_status == "ELIGIBLE":
        explanation += "Candidate meets core preliminary requirements and is ready for shortlisting."
    elif eligibility_status == "NEEDS_REVIEW":
        explanation += "Candidate has partial claims and requires recruiter/hiring manager review before shortlisting."
    else:
        explanation += "Candidate lacks essential required capability signals."

    # Synchronize screening status on application if still PENDING
    if application.screening_status == "PENDING":
        application.screening_status = eligibility_status
        await session.commit()

    return CandidateScreeningResult(
        application_id=application.id,
        candidate_id=candidate.id,
        candidate_name=candidate.full_name,
        candidate_email=candidate.email,
        job_id=job.id,
        job_title=job.title,
        eligibility_status=eligibility_status,
        screening_status=application.screening_status,
        shortlist_status=application.shortlist_status,
        requirements_evaluated=evaluations,
        claims_summary=claims_summary,
        unknowns_summary=unknowns_summary,
        missing_information=missing_info,
        summary_explanation=explanation,
        evaluated_at=datetime.utcnow(),
    )


async def apply_shortlist_decision(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    decision: str,
    reason: str | None = None,
) -> ShortlistDecisionResponse:
    """Applies a human HR/Hiring Manager shortlist decision (SHORTLISTED, NOT_SHORTLISTED, HOLD)."""
    decision_clean = decision.strip().upper()
    if decision_clean not in VALID_SHORTLIST_DECISIONS:
        raise InvalidShortlistDecisionError(
            f"Invalid decision '{decision}'. Must be one of: {', '.join(sorted(VALID_SHORTLIST_DECISIONS))}"
        )

    stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found or inaccessible")

    application.shortlist_status = decision_clean
    application.status = decision_clean
    application.shortlist_reason = reason

    if decision_clean == "SHORTLISTED":
        application.shortlisted_at = datetime.utcnow()
    else:
        application.shortlisted_at = None

    await session.commit()
    await session.refresh(application)

    return ShortlistDecisionResponse(
        application_id=application.id,
        status=application.status,
        screening_status=application.screening_status,
        shortlist_status=application.shortlist_status,
        shortlist_reason=application.shortlist_reason,
        shortlisted_at=application.shortlisted_at,
        is_interview_ready=(decision_clean == "SHORTLISTED"),
    )


async def list_job_candidates_with_screening(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> list[JobCandidateListItem]:
    """Lists all candidates and application screening states for a job under tenant isolation."""
    job_stmt = select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
    job = await session.scalar(job_stmt)
    if not job:
        raise JobNotFoundError("Job not found or inaccessible")

    stmt = (
        select(Application)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(Application.job_id == job_id)
        .options(selectinload(Application.candidate))
        .order_by(Application.created_at.desc())
    )
    apps = list((await session.scalars(stmt)).all())

    results: list[JobCandidateListItem] = []
    for app in apps:
        cand = app.candidate
        has_resume = bool(app.resume_text and app.resume_text.strip())
        is_ready = bool(app.shortlist_status == "SHORTLISTED" or app.status == "SHORTLISTED")
        results.append(
            JobCandidateListItem(
                application_id=app.id,
                candidate_id=cand.id,
                candidate_name=cand.full_name,
                candidate_email=cand.email,
                status=app.status,
                screening_status=app.screening_status,
                shortlist_status=app.shortlist_status,
                applied_at=app.applied_at,
                has_resume=has_resume,
                is_interview_ready=is_ready,
            )
        )

    return results
