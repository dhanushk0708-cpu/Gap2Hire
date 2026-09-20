from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.interview_analysis import PreInterviewAnalysis, PreInterviewCapabilityStatus
from app.services.application import ApplicationNotFoundError


async def build_pre_interview_analysis(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> PreInterviewAnalysis:
    app_stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(app_stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found or inaccessible")

    # Load job capabilities
    caps_stmt = (
        select(Capability)
        .where(Capability.job_id == application.job_id)
        .order_by(Capability.name.asc())
    )
    capabilities = list((await session.scalars(caps_stmt)).all())

    # Load evidence for this application
    ev_stmt = select(Evidence).where(Evidence.application_id == application_id)
    evidences = list((await session.scalars(ev_stmt)).all())
    evidence_by_cap = {e.capability_id: e for e in evidences}

    # Load verifications for this application
    ver_stmt = select(Verification).where(Verification.application_id == application_id)
    verifications = list((await session.scalars(ver_stmt)).all())
    ver_by_cap = {v.capability_id: v for v in verifications}

    known: list[PreInterviewCapabilityStatus] = []
    uncertain: list[PreInterviewCapabilityStatus] = []
    unknown: list[PreInterviewCapabilityStatus] = []
    claims_to_verify: list[dict] = []
    recommended_focus: list[dict] = []

    for cap in capabilities:
        ev = evidence_by_cap.get(cap.id)
        ver = ver_by_cap.get(cap.id)

        has_verified_pass = ver is not None and ver.result == "PASS"
        has_claim = ev is not None and ev.provenance == "CLAIM" and ev.strength in {"STRONG", "MODERATE"}
        has_insufficient = ev is None or ev.strength == "INSUFFICIENT" or ev.content is None

        if has_verified_pass:
            status = "KNOWN"
            prov = "VERIFIED"
            strength = "STRONG"
            rationale = "Capability has been verified through structured verification."
            known.append(
                PreInterviewCapabilityStatus(
                    capability_id=str(cap.id),
                    capability_name=cap.name,
                    importance=cap.importance,
                    provenance=prov,
                    evidence_strength=strength,
                    status=status,
                    rationale=rationale,
                )
            )
        elif has_claim:
            status = "UNCERTAIN"
            prov = "CLAIM"
            strength = ev.strength
            rationale = "Self-reported resume claim requiring targeted interview evaluation."
            uncertain.append(
                PreInterviewCapabilityStatus(
                    capability_id=str(cap.id),
                    capability_name=cap.name,
                    importance=cap.importance,
                    provenance=prov,
                    evidence_strength=strength,
                    status=status,
                    rationale=rationale,
                )
            )
            claims_to_verify.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "claim_content": ev.content if ev else "",
                "importance": cap.importance,
                "priority": "HIGH" if cap.importance in {"HIGH", "CRITICAL"} else "MEDIUM",
            })
            recommended_focus.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "priority": "HIGH" if cap.importance in {"HIGH", "CRITICAL"} else "MEDIUM",
                "focus_type": "VERIFY_CLAIM",
                "reason": f"Verify unproven claim for {cap.name}",
            })
        else:
            status = "UNKNOWN"
            prov = "CLAIM"
            strength = "INSUFFICIENT"
            rationale = "Insufficient or missing evidence from resume."
            unknown.append(
                PreInterviewCapabilityStatus(
                    capability_id=str(cap.id),
                    capability_name=cap.name,
                    importance=cap.importance,
                    provenance=prov,
                    evidence_strength=strength,
                    status=status,
                    rationale=rationale,
                )
            )
            recommended_focus.append({
                "capability_id": str(cap.id),
                "capability_name": cap.name,
                "priority": "MEDIUM",
                "focus_type": "PROBE_UNKNOWN",
                "reason": f"Probe unknown capability {cap.name} for foundational competency",
            })

    # Sort recommended focus by priority: HIGH first, then MEDIUM
    recommended_focus.sort(key=lambda x: 0 if x["priority"] == "HIGH" else 1)

    return PreInterviewAnalysis(
        application_id=application_id,
        job_id=application.job_id,
        known_capabilities=known,
        uncertain_capabilities=uncertain,
        unknown_capabilities=unknown,
        claims_to_verify=claims_to_verify,
        recommended_focus=recommended_focus,
    )
