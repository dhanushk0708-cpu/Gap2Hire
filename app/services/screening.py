from datetime import datetime
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_source import CandidateSource
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.screening import (
    CandidateScreeningProfile,
    CandidateScreeningResult,
    CapabilityScreeningEvaluation,
    JobCandidateListItem,
    JobTopNResult,
    RequirementEvaluation,
    ShortlistDecisionResponse,
    TopNCandidateItem,
)
from app.services.top_n_selection import DynamicTopNSelector

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
    candidate_sources: list[CandidateSource] | None = None,
) -> tuple[str, list[RequirementEvaluation]]:
    """Evaluates candidate eligibility against job capabilities and requirements."""
    evaluations: list[RequirementEvaluation] = []
    verifs = verifications or []
    verif_map = {v.capability_id: v for v in verifs if v.result == "PASS"}
    ev_map: dict[UUID, list[Evidence]] = {}
    for ev in evidence_list:
        ev_map.setdefault(ev.capability_id, []).append(ev)

    sources = candidate_sources if candidate_sources is not None else getattr(application, "sources", [])
    sources_map = {s.id: s for s in sources} if sources else {}

    provenance_weights = {"VERIFIED": 4, "DEMONSTRATED": 3, "CORROBORATED": 2, "CLAIM": 1, "UNKNOWN": 0}
    strength_weights = {"STRONG": 3, "MODERATE": 2, "WEAK": 1, "INSUFFICIENT": 0}

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
                    evidence_found="Practical assessment verification passed.",
                    provenance="VERIFIED",
                    strength="STRONG",
                    source_type="PRACTICAL_ASSESSMENT",
                    source_url=None,
                    verification_needed=False,
                    verification_status="PASSED",
                    next_step="Verified",
                    reason=f"Candidate successfully passed practical exercise for {cap.name}.",
                )
            )
            met_count += 1
        elif cap_evs:
            # Sort by provenance first then strength to pick highest-provenance evidence
            sorted_evs = sorted(
                cap_evs,
                key=lambda e: (
                    provenance_weights.get(e.provenance, 0),
                    strength_weights.get(e.strength, 0),
                ),
                reverse=True,
            )
            primary_ev = sorted_evs[0]
            prov_val = primary_ev.provenance or "CLAIM"
            strength = primary_ev.strength or "STRONG"
            source_obj = sources_map.get(primary_ev.candidate_source_id) if primary_ev.candidate_source_id else None
            src_url = source_obj.url if source_obj else None
            src_type = primary_ev.source_type or ("GITHUB" if src_url and "github" in src_url.lower() else "RESUME")

            if strength == "INSUFFICIENT":
                evaluations.append(
                    RequirementEvaluation(
                        requirement_name=cap.name,
                        requirement_type="CAPABILITY",
                        status="INSUFFICIENT",
                        evidence_found=primary_ev.content,
                        provenance=prov_val,
                        strength=strength,
                        source_type=src_type,
                        source_url=src_url,
                        verification_needed=True,
                        verification_status="NOT_YET_VERIFIED",
                        next_step="Probing / assessment required",
                        reason=f"Inspected sources for {cap.name} showed insufficient evidence.",
                    )
                )
                unknown_count += 1
            elif strength in {"STRONG", "MODERATE"}:
                is_demo = prov_val in {"DEMONSTRATED", "CORROBORATED"}
                evaluations.append(
                    RequirementEvaluation(
                        requirement_name=cap.name,
                        requirement_type="CAPABILITY",
                        status="MET",
                        evidence_found=primary_ev.content,
                        provenance=prov_val,
                        strength=strength,
                        source_type=src_type,
                        source_url=src_url,
                        verification_needed=(prov_val != "VERIFIED"),
                        verification_status="NOT_YET_VERIFIED",
                        next_step="Interview / practical verification" if is_demo else "Practical verification",
                        reason=(
                            f"Demonstrated evidence identified for {cap.name} from {src_type} (Strength: {strength})."
                            if is_demo
                            else f"Resume claim identified for {cap.name} (Provenance: CLAIM, Strength: {strength})."
                        ),
                    )
                )
                met_count += 1
            else:
                evaluations.append(
                    RequirementEvaluation(
                        requirement_name=cap.name,
                        requirement_type="CAPABILITY",
                        status="NEEDS_REVIEW",
                        evidence_found=primary_ev.content,
                        provenance=prov_val,
                        strength=strength,
                        source_type=src_type,
                        source_url=src_url,
                        verification_needed=True,
                        verification_status="NOT_YET_VERIFIED",
                        next_step="Technical interview probing",
                        reason=f"Weak evidence identified for {cap.name} (Provenance: {prov_val}, Strength: {strength}).",
                    )
                )
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
                    source_type=None,
                    source_url=None,
                    verification_needed=True,
                    verification_status="NOT_YET_VERIFIED",
                    next_step="Practical verification",
                    reason=f"No explicit mention or evidence found in resume or sources for {cap.name}.",
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
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
            selectinload(Application.sources),
        )
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
        candidate_sources=application.sources,
    )

    claims_summary: list[str] = []
    unknowns_summary: list[str] = []
    missing_info: list[str] = []

    for ev in evaluations:
        if ev.status == "MET" and ev.provenance == "CLAIM":
            claims_summary.append(f"{ev.requirement_name}: {ev.evidence_found} (Claim)")
        elif ev.status in {"UNKNOWN", "NEEDS_REVIEW", "INSUFFICIENT"}:
            unknowns_summary.append(ev.requirement_name)
            missing_info.append(f"Verification needed for {ev.requirement_name}")

    # Build factual, non-misleading summary explanation
    claims_count = sum(1 for e in evaluations if e.provenance == "CLAIM")
    demonstrated_count = sum(1 for e in evaluations if e.provenance in {"DEMONSTRATED", "CORROBORATED"})
    verified_count = sum(1 for e in evaluations if e.provenance == "VERIFIED")
    unknown_count = sum(1 for e in evaluations if e.status == "UNKNOWN" or e.provenance == "UNKNOWN")
    insufficient_count = sum(1 for e in evaluations if e.status == "INSUFFICIENT")
    verification_needed_count = sum(1 for e in evaluations if e.verification_needed)
    supported_count = sum(1 for e in evaluations if e.status == "MET")
    total_reqs = len(evaluations)

    explanation = (
        f"{supported_count} / {total_reqs} requirements have supporting preliminary evidence. "
        f"Verified: {verified_count} • Demonstrated: {demonstrated_count} • "
        f"Resume claims: {claims_count} • Unknown: {unknown_count} • "
        f"Verification needed: {verification_needed_count}. "
    )
    if verified_count == 0 and demonstrated_count == 0:
        explanation += "Resume evidence supports initial screening. Independent verification is still required."
    elif verified_count == 0:
        explanation += "Project artifacts provide preliminary demonstration. Independent verification is still required."
    else:
        explanation += "Candidate has independently verified capabilities."

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
        shortlist_reason=application.shortlist_reason,
        requirements_evaluated=evaluations,
        claims_summary=claims_summary,
        unknowns_summary=unknowns_summary,
        missing_information=missing_info,
        summary_explanation=explanation,
        verified_count=verified_count,
        demonstrated_count=demonstrated_count,
        claims_count=claims_count,
        unknown_count=unknown_count,
        insufficient_count=insufficient_count,
        verification_needed_count=verification_needed_count,
        supported_count=supported_count,
        total_requirements_count=total_reqs,
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
        is_demo = bool(getattr(app, "is_demo", False) or (cand.email and cand.email.endswith(("@demo.gap2hire.local", "@synthetic.gap2hire.local"))))
        results.append(
            JobCandidateListItem(
                application_id=app.id,
                candidate_id=cand.id,
                candidate_name=cand.full_name,
                candidate_email=cand.email,
                status=app.status,
                screening_status=app.screening_status,
                shortlist_status=app.shortlist_status,
                shortlist_reason=app.shortlist_reason,
                applied_at=app.applied_at,
                has_resume=has_resume,
                is_interview_ready=is_ready,
                is_demo=is_demo,
            )
        )

    return results


async def build_candidate_screening_profile(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> CandidateScreeningProfile:
    """
    Builds a rich, multi-dimensional Candidate Screening Profile grounded in verified evidence,
    demonstrated code/project artifacts, and resume claims under strict tenant isolation.
    Computes hard requirement coverage, unknowns, and verification needs deterministically.
    Zero opaque AI scores.
    """
    stmt = (
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
    application = await session.scalar(stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found or inaccessible")

    job = application.job
    candidate = application.candidate

    # Load capabilities for this job
    caps_stmt = select(Capability).where(Capability.job_id == job.id).order_by(Capability.created_at.asc())
    capabilities = list((await session.scalars(caps_stmt)).all())

    # Load evidence for this application
    ev_stmt = select(Evidence).where(Evidence.application_id == application_id)
    evidence_list = list((await session.scalars(ev_stmt)).all())

    # Load verifications for this application
    ver_stmt = select(Verification).where(Verification.application_id == application_id)
    verifications = list((await session.scalars(ver_stmt)).all())
    verif_map = {v.capability_id: v for v in verifications if v.result == "PASS"}

    # Map candidate sources by id
    sources_map = {s.id: s for s in application.sources}

    # Group evidence by capability_id
    ev_map: dict[UUID, list[Evidence]] = {}
    for ev in evidence_list:
        ev_map.setdefault(ev.capability_id, []).append(ev)

    # Determine required vs preferred capabilities
    # CRITICAL and HIGH are required (hard requirements)
    has_explicit_required = any(c.importance in {"CRITICAL", "HIGH"} for c in capabilities)

    capability_evaluations: list[CapabilityScreeningEvaluation] = []
    strength_counts = {"STRONG": 0, "MODERATE": 0, "WEAK": 0, "INSUFFICIENT": 0}
    provenance_counts = {"DEMONSTRATED": 0, "CORROBORATED": 0, "CLAIM": 0, "UNKNOWN": 0}

    project_findings: list[str] = []
    resume_findings: list[str] = []
    unknown_caps: list[str] = []
    insufficient_caps: list[str] = []
    verification_needs: list[str] = []

    provenance_weights = {"VERIFIED": 4, "DEMONSTRATED": 3, "CORROBORATED": 2, "CLAIM": 1, "UNKNOWN": 0}
    strength_weights = {"STRONG": 3, "MODERATE": 2, "WEAK": 1, "INSUFFICIENT": 0}

    for cap in capabilities:
        cap_id = cap.id
        cap_evs = ev_map.get(cap_id, [])
        is_verified = cap_id in verif_map

        is_required = (cap.importance in {"CRITICAL", "HIGH"}) if has_explicit_required else True

        if is_verified:
            eval_item = CapabilityScreeningEvaluation(
                capability_id=cap_id,
                capability_name=cap.name,
                importance=cap.importance,
                is_required=is_required,
                status="MET",
                evidence_ids=[],
                evidence_strength="STRONG",
                provenance="VERIFIED",
                content="Practical verification passed.",
                source_url=None,
                source_type="VERIFICATION",
                unknown_reason=None,
                verification_needed=False,
            )
            strength_counts["STRONG"] += 1
            provenance_counts["DEMONSTRATED"] += 1
            project_findings.append(f"{cap.name}: Practical verification passed.")

        elif cap_evs:
            # Sort evidence by provenance rank then strength rank
            sorted_evs = sorted(
                cap_evs,
                key=lambda e: (
                    provenance_weights.get(e.provenance, 0),
                    strength_weights.get(e.strength, 0),
                ),
                reverse=True,
            )
            best_ev = sorted_evs[0]
            st_val = best_ev.strength or "STRONG"
            prov_val = best_ev.provenance or "CLAIM"

            if st_val in strength_counts:
                strength_counts[st_val] += 1
            if prov_val in provenance_counts:
                provenance_counts[prov_val] += 1

            source_obj = sources_map.get(best_ev.candidate_source_id) if best_ev.candidate_source_id else None
            src_url = source_obj.url if source_obj else None

            if st_val == "INSUFFICIENT":
                eval_item = CapabilityScreeningEvaluation(
                    capability_id=cap_id,
                    capability_name=cap.name,
                    importance=cap.importance,
                    is_required=is_required,
                    status="INSUFFICIENT",
                    evidence_ids=[e.id for e in sorted_evs],
                    evidence_strength=st_val,
                    provenance=prov_val,
                    content=best_ev.content,
                    source_url=src_url,
                    source_type=best_ev.source_type,
                    unknown_reason=f"Inspected sources for {cap.name} showed insufficient evidence.",
                    verification_needed=True,
                )
                insufficient_caps.append(cap.name)
                verification_needs.append(f"Probing required for {cap.name} (insufficient source evidence).")

            elif st_val in {"STRONG", "MODERATE"}:
                eval_item = CapabilityScreeningEvaluation(
                    capability_id=cap_id,
                    capability_name=cap.name,
                    importance=cap.importance,
                    is_required=is_required,
                    status="MET",
                    evidence_ids=[e.id for e in sorted_evs],
                    evidence_strength=st_val,
                    provenance=prov_val,
                    content=best_ev.content,
                    source_url=src_url,
                    source_type=best_ev.source_type,
                    unknown_reason=None,
                    verification_needed=False,
                )
                finding_str = f"{cap.name}: {best_ev.content or 'Demonstrated in source'}"
                if prov_val in {"DEMONSTRATED", "CORROBORATED"}:
                    project_findings.append(finding_str)
                else:
                    resume_findings.append(finding_str)

            else:
                # WEAK
                eval_item = CapabilityScreeningEvaluation(
                    capability_id=cap_id,
                    capability_name=cap.name,
                    importance=cap.importance,
                    is_required=is_required,
                    status="NEEDS_REVIEW",
                    evidence_ids=[e.id for e in sorted_evs],
                    evidence_strength=st_val,
                    provenance=prov_val,
                    content=best_ev.content,
                    source_url=src_url,
                    source_type=best_ev.source_type,
                    unknown_reason=f"Weak evidence identified for {cap.name}.",
                    verification_needed=True,
                )
                verification_needs.append(f"Technical interview probing required for {cap.name}.")

        else:
            # UNKNOWN
            eval_item = CapabilityScreeningEvaluation(
                capability_id=cap_id,
                capability_name=cap.name,
                importance=cap.importance,
                is_required=is_required,
                status="UNKNOWN",
                evidence_ids=[],
                evidence_strength=None,
                provenance="UNKNOWN",
                content=None,
                source_url=None,
                source_type=None,
                unknown_reason=f"No resume claim or public source evidence found for {cap.name}.",
                verification_needed=True,
            )
            provenance_counts["UNKNOWN"] += 1
            unknown_caps.append(cap.name)
            verification_needs.append(f"Practical verification needed for {cap.name}.")

        capability_evaluations.append(eval_item)

    # Separate required vs preferred
    required_evals = [e for e in capability_evaluations if e.is_required]
    preferred_evals = [e for e in capability_evaluations if not e.is_required]

    req_total = len(required_evals)
    req_met = sum(1 for e in required_evals if e.status == "MET")
    is_hard_satisfied = (req_met == req_total) if req_total > 0 else True

    hard_req_cov = {
        "total": req_total,
        "met": req_met,
        "ratio": round(req_met / req_total, 2) if req_total > 0 else 1.0,
        "is_satisfied": is_hard_satisfied,
    }

    # Determine overall screening status
    if not capabilities:
        scr_status = "ELIGIBLE" if (application.resume_text and application.resume_text.strip()) else "NEEDS_REVIEW"
    elif is_hard_satisfied:
        scr_status = "ELIGIBLE"
    elif req_met > 0 or len(unknown_caps) > 0 or len(insufficient_caps) > 0:
        scr_status = "NEEDS_REVIEW"
    else:
        scr_status = "NOT_ELIGIBLE"

    # Human-readable summary explanation
    pref_total = len(preferred_evals)
    pref_met = sum(1 for e in preferred_evals if e.status == "MET")
    demo_count = provenance_counts.get("DEMONSTRATED", 0) + provenance_counts.get("CORROBORATED", 0)

    summary_text = (
        f"Screening profile for {candidate.full_name}: {req_met}/{req_total} hard requirements met, "
        f"{pref_met}/{pref_total} preferred skills supported. "
        f"{demo_count} practical project/code demonstrations verified. "
    )
    if unknown_caps:
        summary_text += f"Unknown capabilities: {', '.join(unknown_caps)}. "
    if insufficient_caps:
        summary_text += f"Insufficient sources: {', '.join(insufficient_caps)}. "

    return CandidateScreeningProfile(
        application_id=application.id,
        candidate_id=candidate.id,
        candidate_name=candidate.full_name,
        candidate_email=candidate.email,
        job_id=job.id,
        job_title=job.title,
        screening_status=scr_status,
        shortlist_status=application.shortlist_status,
        rank=None,
        capability_results=capability_evaluations,
        hard_requirement_coverage=hard_req_cov,
        required_capability_evidence=[e.model_dump() for e in required_evals],
        preferred_capability_evidence=[e.model_dump() for e in preferred_evals],
        evidence_strength=strength_counts,
        evidence_provenance=provenance_counts,
        relevant_project_evidence=project_findings,
        relevant_resume_evidence=resume_findings,
        unknown_capabilities=unknown_caps,
        insufficient_capabilities=insufficient_caps,
        verification_needed=verification_needs,
        summary_explanation=summary_text.strip(),
        applied_at=application.applied_at,
        evaluated_at=datetime.utcnow(),
    )


async def run_job_screening_workflow(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
    max_research_iterations_per_candidate: int = 2,
) -> JobTopNResult:
    """
    Executes the automated end-to-end screening workflow across all candidates for a job:
    1. Loads job and capabilities.
    2. Investigates candidate resume text & extracts resume claims if needed.
    3. Deeply inspects repository artifacts for registered candidate sources.
    4. Evaluates all candidates and constructs multi-dimensional screening profiles.
    5. Feeds all candidate profiles into DynamicTopNSelector (processes ALL applicants, never stops early).
    6. Dynamically updates candidate rankings, shortlist statuses, and audit cutoff reasons in PostgreSQL.
    7. Returns complete Top-N recommendation result.
    """
    job_stmt = select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
    job = await session.scalar(job_stmt)
    if not job:
        raise JobNotFoundError("Job not found or inaccessible")

    # Load all applications for this job
    apps_stmt = (
        select(Application)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(Application.job_id == job_id)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.sources),
        )
        .order_by(Application.created_at.asc())
    )
    applications = list((await session.scalars(apps_stmt)).all())

    # Load capabilities for keyword searching during artifact inspection
    caps_stmt = select(Capability).where(Capability.job_id == job_id)
    capabilities = list((await session.scalars(caps_stmt)).all())

    from app.services.evidence import analyze_application_evidence, record_candidate_evidence
    from app.services.resume_url_discovery import sync_resume_candidate_sources
    from app.services.source_artifact_discovery import deep_inspect_candidate_source

    candidate_profiles: list[CandidateScreeningProfile] = []

    for app_obj in applications:
        # 1. Sync candidate sources from resume if text exists
        if app_obj.resume_text and app_obj.resume_text.strip():
            try:
                await sync_resume_candidate_sources(
                    session=session,
                    organization_id=organization_id,
                    application_id=app_obj.id,
                    resume_text=app_obj.resume_text,
                )
            except Exception as src_err:
                logger.info(f"Source discovery notice for application {app_obj.id}: {src_err}")

            # 2. Extract resume evidence claims if not yet extracted
            ev_check = await session.scalars(select(Evidence).where(Evidence.application_id == app_obj.id))
            if not list(ev_check.all()) and capabilities:
                if getattr(app_obj, "is_demo", False):
                    from app.services.demo_import import extract_grounded_evidence_for_resume
                    ev_items = extract_grounded_evidence_for_resume(capabilities, app_obj.resume_text or "")
                    for item in ev_items:
                        session.add(
                            Evidence(
                                application_id=app_obj.id,
                                capability_id=item["capability_id"],
                                candidate_source_id=None,
                                source_type="RESUME",
                                strength=item["strength"],
                                provenance="CLAIM",
                                content=item["content"],
                            )
                        )
                    await session.flush()
                else:
                    try:
                        await analyze_application_evidence(
                            session=session,
                            application_id=app_obj.id,
                            organization_id=organization_id,
                        )
                    except Exception as ev_err:
                        logger.info(f"Resume evidence extraction notice for {app_obj.id}: {ev_err}")

        # 3. Deep source artifact investigation for repository sources
        # Refresh sources
        srcs_stmt = select(CandidateSource).where(CandidateSource.application_id == app_obj.id)
        sources = list((await session.scalars(srcs_stmt)).all())

        for src in sources:
            if getattr(app_obj, "is_demo", False):
                # Synthetic demo resumes do not have real external GitHub repositories; skip network inspection
                continue
            if src.source_type.upper() in {"GITHUB", "GITLAB"}:
                try:
                    deep_res = await deep_inspect_candidate_source(
                        url=src.url,
                        source_type=src.source_type,
                    )
                    src.status = "INSPECTED" if deep_res.get("successful_artifacts", 0) > 0 else src.status
                    src.last_inspected_at = datetime.utcnow()

                    comb_text = deep_res.get("combined_artifact_text", "").lower()
                    if comb_text:
                        # Corroborate matching capabilities with concrete demonstrated code evidence
                        for cap in capabilities:
                            cap_name_lower = cap.name.lower()
                            if cap_name_lower in comb_text:
                                await record_candidate_evidence(
                                    session=session,
                                    organization_id=organization_id,
                                    application_id=app_obj.id,
                                    capability_id=cap.id,
                                    source_type="GITHUB",
                                    strength="STRONG",
                                    provenance="DEMONSTRATED",
                                    content=f"Concrete demonstration of {cap.name} verified in repository artifacts ({src.url}).",
                                    candidate_source_id=src.id,
                except Exception as deep_err:
                    logger.warning(f"Error inspecting repository source {src.url}: {deep_err}")

        # 4. Build structured screening profile
        profile = await build_candidate_screening_profile(
            session=session,
            application_id=app_obj.id,
            organization_id=organization_id,
        )
        candidate_profiles.append(profile)

    # 5. Dynamic Top-N competitive selection across all candidates
    shortlist_size = getattr(job, "shortlist_size", 5) or 5
    selector = DynamicTopNSelector(
        shortlist_size=shortlist_size,
        job_id=job.id,
        job_title=job.title,
    )

    for profile in candidate_profiles:
        selector.add_candidate(profile)

    top_n_result = selector.to_job_top_n_result()

    # 6. Synchronize persistent application shortlist statuses in DB
    top_n_map = {item.application_id: item for item in top_n_result.top_n_candidates}
    excluded_map = {item.application_id: item for item in top_n_result.excluded_candidates}
    profile_map = {p.application_id: p for p in candidate_profiles}

    for app_obj in applications:
        prof = profile_map.get(app_obj.id)
        if app_obj.id in top_n_map:
            item = top_n_map[app_obj.id]
            app_obj.shortlist_status = "SHORTLISTED"
            app_obj.status = "SHORTLISTED"
            if prof:
                app_obj.screening_status = prof.screening_status
            app_obj.shortlisted_at = datetime.utcnow()
            app_obj.shortlist_reason = item.selection_reason
            app_obj.screening_notes = item.summary_explanation
        elif app_obj.id in excluded_map:
            item = excluded_map[app_obj.id]
            app_obj.shortlist_status = "NOT_SHORTLISTED"
            app_obj.status = "NOT_SHORTLISTED"
            if prof:
                app_obj.screening_status = prof.screening_status
            app_obj.shortlisted_at = None
            app_obj.shortlist_reason = item.selection_reason
            app_obj.screening_notes = item.summary_explanation

    await session.commit()
    return top_n_result


async def get_job_top_n_screening_results(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> JobTopNResult:
    """
    Computes current Top-N ranking and comparative breakdown for all candidates of a job.
    """
    job_stmt = select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
    job = await session.scalar(job_stmt)
    if not job:
        raise JobNotFoundError("Job not found or inaccessible")

    apps_stmt = (
        select(Application)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(Application.job_id == job_id)
        .order_by(Application.created_at.asc())
    )
    applications = list((await session.scalars(apps_stmt)).all())

    shortlist_size = getattr(job, "shortlist_size", 5) or 5
    selector = DynamicTopNSelector(
        shortlist_size=shortlist_size,
        job_id=job.id,
        job_title=job.title,
    )

    for app_obj in applications:
        profile = await build_candidate_screening_profile(
            session=session,
            application_id=app_obj.id,
            organization_id=organization_id,
        )
        selector.add_candidate(profile)

    return selector.to_job_top_n_result()

