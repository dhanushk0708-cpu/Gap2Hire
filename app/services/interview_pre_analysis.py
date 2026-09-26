from datetime import datetime
from typing import Any
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
from app.schemas.interview_analysis import (
    CandidateInterviewPreAnalysis,
    PreInterviewAnalysis,
    PreInterviewCapabilityStatus,
)
from app.services.application import ApplicationNotFoundError


async def build_candidate_interview_pre_analysis(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> CandidateInterviewPreAnalysis:
    """
    Constructs a grounded, multi-dimensional Pre-Interview Analysis for a candidate:
    - Distinguishes resume CLAIM from DEMONSTRATED or VERIFIED evidence.
    - Preserves provenance semantics: CLAIM, DEMONSTRATED, CORROBORATED, VERIFIED, UNKNOWN, INSUFFICIENT.
    - Zero opaque scores, no invented candidate experience.
    - Pinpoints exact verification targets and uncertainties for candidate-specific interview planning.
    """
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
        raise ApplicationNotFoundError("Application not found or inaccessible")

    candidate = application.candidate
    job = application.job

    # Load job capabilities ordered by importance
    caps_stmt = (
        select(Capability)
        .where(Capability.job_id == job.id)
        .order_by(Capability.created_at.asc())
    )
    capabilities = list((await session.scalars(caps_stmt)).all())

    # Load evidence for this application
    ev_stmt = select(Evidence).where(Evidence.application_id == application_id)
    evidences = list((await session.scalars(ev_stmt)).all())

    # Group evidence by capability_id
    evidence_by_cap: dict[UUID, list[Evidence]] = {}
    for e in evidences:
        evidence_by_cap.setdefault(e.capability_id, []).append(e)

    # Load verifications for this application
    ver_stmt = select(Verification).where(Verification.application_id == application_id)
    verifications = list((await session.scalars(ver_stmt)).all())
    ver_by_cap = {v.capability_id: v for v in verifications if v.result == "PASS"}

    # Sources map
    sources_map = {s.id: s for s in application.sources}

    candidate_strengths: list[dict[str, Any]] = []
    candidate_claims: list[dict[str, Any]] = []
    candidate_unknowns: list[dict[str, Any]] = []
    verification_targets: list[dict[str, Any]] = []
    recommended_focus: list[dict[str, Any]] = []
    existing_evidence_references: list[dict[str, Any]] = []
    relevant_concepts: list[str] = [c.name for c in capabilities]

    for cap in capabilities:
        cap_ev_list = evidence_by_cap.get(cap.id, [])
        ver = ver_by_cap.get(cap.id)

        # Look for strongest evidence
        demonstrated_ev = next(
            (e for e in cap_ev_list if e.provenance in {"DEMONSTRATED", "CORROBORATED"} and e.strength in {"STRONG", "MODERATE"}),
            None,
        )
        claim_ev = next(
            (e for e in cap_ev_list if e.provenance == "CLAIM" and e.strength in {"STRONG", "MODERATE"}),
            None,
        )

        # 1. VERIFIED
        if ver is not None:
            candidate_strengths.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "importance": cap.importance,
                "provenance": "VERIFIED",
                "evidence_strength": "STRONG",
                "status": "KNOWN",
                "rationale": f"Capability {cap.name} verified through practical assessment ({ver.verification_type}).",
                "source_type": "ASSESSMENT",
                "source_url": None,
            })
            existing_evidence_references.append({
                "capability_name": cap.name,
                "provenance": "VERIFIED",
                "reference_type": "VERIFICATION",
                "content": f"Verified in {ver.verification_type} assessment with score {ver.score}.",
            })

        # 2. DEMONSTRATED / CORROBORATED
        elif demonstrated_ev is not None:
            src_obj = sources_map.get(demonstrated_ev.candidate_source_id) if demonstrated_ev.candidate_source_id else None
            src_url = src_obj.url if src_obj else None
            candidate_strengths.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "importance": cap.importance,
                "provenance": demonstrated_ev.provenance,
                "evidence_strength": demonstrated_ev.strength,
                "status": "KNOWN",
                "rationale": f"Concrete demonstration of {cap.name} identified in candidate source artifacts.",
                "source_type": demonstrated_ev.source_type,
                "source_url": src_url,
            })
            existing_evidence_references.append({
                "capability_name": cap.name,
                "provenance": demonstrated_ev.provenance,
                "reference_type": "SOURCE_ARTIFACT",
                "content": demonstrated_ev.content,
                "source_url": src_url,
            })

        # 3. CLAIM ONLY (Self-reported in resume, not yet verified)
        elif claim_ev is not None:
            claim_info = {
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "importance": cap.importance,
                "provenance": "CLAIM",
                "evidence_strength": claim_ev.strength,
                "status": "UNCERTAIN",
                "rationale": f"{cap.name} is currently a self-reported resume CLAIM requiring interview verification.",
                "source_type": "RESUME",
                "claim_content": claim_ev.content,
            }
            candidate_claims.append(claim_info)
            verification_targets.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "importance": cap.importance,
                "current_state": "CLAIM",
                "priority": "HIGH" if cap.importance in {"CRITICAL", "HIGH"} else "MEDIUM",
                "verification_reason": f"{cap.name} is stated on resume but lacks independent verification.",
            })
            recommended_focus.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "priority": "HIGH" if cap.importance in {"CRITICAL", "HIGH"} else "MEDIUM",
                "focus_type": "VERIFY_CLAIM",
                "reason": f"{cap.name} is currently CLAIM and should be verified during interview.",
            })
            existing_evidence_references.append({
                "capability_name": cap.name,
                "provenance": "CLAIM",
                "reference_type": "RESUME_CLAIM",
                "content": claim_ev.content,
            })

        # 4. UNKNOWN / INSUFFICIENT
        else:
            unknown_info = {
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "importance": cap.importance,
                "provenance": "UNKNOWN",
                "evidence_strength": "INSUFFICIENT",
                "status": "UNKNOWN",
                "rationale": f"No explicit mention or evidence found for {cap.name}.",
            }
            candidate_unknowns.append(unknown_info)
            verification_targets.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "importance": cap.importance,
                "current_state": "UNKNOWN",
                "priority": "HIGH" if cap.importance in {"CRITICAL", "HIGH"} else "MEDIUM",
                "verification_reason": f"No prior evidence for required capability {cap.name}; probe foundational knowledge.",
            })
            recommended_focus.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "priority": "HIGH" if cap.importance in {"CRITICAL", "HIGH"} else "MEDIUM",
                "focus_type": "PROBE_UNKNOWN",
                "reason": f"Probe unknown capability {cap.name} to determine competency.",
            })

    # Sort verification targets and recommended focus by priority: HIGH first, then MEDIUM
    verification_targets.sort(key=lambda x: 0 if x["priority"] == "HIGH" else 1)
    recommended_focus.sort(key=lambda x: 0 if x["priority"] == "HIGH" else 1)

    # Build grounded textual summary
    summary_parts = []
    if candidate_strengths:
        str_names = [f"{s['capability_name']} ({s['provenance']})" for s in candidate_strengths]
        summary_parts.append(f"Demonstrated Competencies: {', '.join(str_names)}.")
    if candidate_claims:
        clm_names = [f"{c['capability_name']} (CLAIM)" for c in candidate_claims]
        summary_parts.append(f"Unverified Resume Claims: {', '.join(clm_names)} - verification recommended.")
    if candidate_unknowns:
        unk_names = [f"{u['capability_name']} (UNKNOWN)" for u in candidate_unknowns]
        summary_parts.append(f"Unknown Capabilities: {', '.join(unk_names)} - exploratory probing recommended.")

    grounded_summary = " ".join(summary_parts) if summary_parts else "Candidate evaluation pending."

    return CandidateInterviewPreAnalysis(
        application_id=application_id,
        candidate_id=candidate.id,
        candidate_name=candidate.full_name,
        candidate_email=candidate.email,
        job_id=job.id,
        job_title=job.title,
        candidate_strengths=candidate_strengths,
        candidate_claims=candidate_claims,
        candidate_unknowns=candidate_unknowns,
        verification_targets=verification_targets,
        relevant_concepts=relevant_concepts,
        recommended_focus=recommended_focus,
        existing_evidence_references=existing_evidence_references,
        grounded_summary=grounded_summary,
        created_at=datetime.utcnow(),
    )


async def build_pre_interview_analysis(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> PreInterviewAnalysis:
    """
    Backwards-compatible wrapper returning PreInterviewAnalysis with all rich fields populated.
    """
    rich_analysis = await build_candidate_interview_pre_analysis(
        session=session,
        application_id=application_id,
        organization_id=organization_id,
    )

    known: list[PreInterviewCapabilityStatus] = [
        PreInterviewCapabilityStatus(
            capability_id=s["capability_id"],
            capability_name=s["capability_name"],
            importance=s["importance"],
            provenance=s["provenance"],
            evidence_strength=s["evidence_strength"],
            status=s["status"],
            rationale=s["rationale"],
            source_type=s.get("source_type"),
            source_url=s.get("source_url"),
        )
        for s in rich_analysis.candidate_strengths
    ]

    uncertain: list[PreInterviewCapabilityStatus] = [
        PreInterviewCapabilityStatus(
            capability_id=c["capability_id"],
            capability_name=c["capability_name"],
            importance=c["importance"],
            provenance=c["provenance"],
            evidence_strength=c["evidence_strength"],
            status=c["status"],
            rationale=c["rationale"],
            source_type=c.get("source_type"),
        )
        for c in rich_analysis.candidate_claims
    ]

    unknown: list[PreInterviewCapabilityStatus] = [
        PreInterviewCapabilityStatus(
            capability_id=u["capability_id"],
            capability_name=u["capability_name"],
            importance=u["importance"],
            provenance=u["provenance"],
            evidence_strength=u["evidence_strength"],
            status=u["status"],
            rationale=u["rationale"],
        )
        for u in rich_analysis.candidate_unknowns
    ]

    return PreInterviewAnalysis(
        application_id=rich_analysis.application_id,
        job_id=rich_analysis.job_id,
        known_capabilities=known,
        uncertain_capabilities=uncertain,
        unknown_capabilities=unknown,
        claims_to_verify=[
            {"capability_id": c["capability_id"], "capability_name": c["capability_name"], "claim_content": c.get("claim_content", "")}
            for c in rich_analysis.candidate_claims
        ],
        recommended_focus=rich_analysis.recommended_focus,
        candidate_strengths=rich_analysis.candidate_strengths,
        candidate_claims=rich_analysis.candidate_claims,
        candidate_unknowns=rich_analysis.candidate_unknowns,
        verification_targets=rich_analysis.verification_targets,
        relevant_concepts=rich_analysis.relevant_concepts,
        existing_evidence_references=rich_analysis.existing_evidence_references,
        grounded_summary=rich_analysis.grounded_summary,
        created_at=rich_analysis.created_at,
    )
