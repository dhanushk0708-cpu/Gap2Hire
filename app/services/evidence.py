from collections.abc import Sequence
from datetime import datetime
from typing import Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.capability import Capability
from app.models.candidate_source import CandidateSource
from app.models.evidence import Evidence
from app.models.job import Job
from app.schemas.evidence import (
    ApplicationEvidenceSummary,
    CapabilityEvidenceState,
    CapabilityEvidenceSummary,
    EvidenceProvenance,
    EvidenceStrength,
)
from app.services.ai_evidence import extract_evidence_from_resume
from app.services.application import ApplicationNotFoundError


class NoProcessedResumeError(Exception):
    pass


class NoApprovedCapabilitiesError(Exception):
    pass


class CapabilityNotFoundError(Exception):
    pass


class CandidateSourceNotFoundError(Exception):
    pass


class InvalidCandidateSourceError(Exception):
    pass


async def _get_tenant_application(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> Application:
    """Verifies that the application exists and belongs to the given tenant organization."""
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
        raise ApplicationNotFoundError("Application not found")
    return application


async def record_candidate_evidence(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    application_id: Union[UUID, str],
    capability_id: Union[UUID, str],
    source_type: str,
    strength: Union[str, EvidenceStrength],
    provenance: Union[str, EvidenceProvenance] = EvidenceProvenance.CLAIM,
    content: Optional[str] = None,
    candidate_source_id: Optional[Union[UUID, str]] = None,
) -> Evidence:
    """
    Creates or updates a structured evidence record attached to an application and capability,
    optionally referencing a verified CandidateSource provenance under strict tenant isolation.
    """
    org_uuid = UUID(str(organization_id)) if not isinstance(organization_id, UUID) else organization_id
    app_uuid = UUID(str(application_id)) if not isinstance(application_id, UUID) else application_id
    cap_uuid = UUID(str(capability_id)) if not isinstance(capability_id, UUID) else capability_id
    cand_src_uuid = (
        UUID(str(candidate_source_id))
        if candidate_source_id is not None and not isinstance(candidate_source_id, UUID)
        else candidate_source_id
    )

    application = await _get_tenant_application(session, app_uuid, org_uuid)

    # Verify capability belongs to this application's job
    cap_stmt = select(Capability).where(
        Capability.id == cap_uuid,
        Capability.job_id == application.job_id,
    )
    capability = await session.scalar(cap_stmt)
    if capability is None:
        raise CapabilityNotFoundError(f"Capability {cap_uuid} not found for this application's job")

    # If candidate_source_id is provided, verify it exists and belongs to the same application
    if cand_src_uuid is not None:
        src_stmt = select(CandidateSource).where(CandidateSource.id == cand_src_uuid)
        source = await session.scalar(src_stmt)
        if source is None:
            raise CandidateSourceNotFoundError(f"Candidate source {cand_src_uuid} not found")
        if source.application_id != app_uuid:
            raise InvalidCandidateSourceError(
                f"Candidate source {cand_src_uuid} belongs to a different application"
            )

    strength_val = strength.value if isinstance(strength, EvidenceStrength) else str(strength)
    provenance_val = provenance.value if isinstance(provenance, EvidenceProvenance) else str(provenance)

    # Check for existing evidence under (application_id, capability_id, source_type)
    ev_stmt = select(Evidence).where(
        Evidence.application_id == app_uuid,
        Evidence.capability_id == cap_uuid,
        Evidence.source_type == source_type,
    )
    existing_ev = await session.scalar(ev_stmt)

    if existing_ev is not None:
        existing_ev.strength = strength_val
        existing_ev.provenance = provenance_val
        existing_ev.content = content
        existing_ev.candidate_source_id = cand_src_uuid
        existing_ev.updated_at = datetime.utcnow()
        evidence_record = existing_ev
    else:
        new_ev = Evidence(
            application_id=app_uuid,
            capability_id=cap_uuid,
            candidate_source_id=cand_src_uuid,
            source_type=source_type,
            strength=strength_val,
            provenance=provenance_val,
            content=content,
        )
        session.add(new_ev)
        evidence_record = new_ev

    await session.commit()
    await session.refresh(evidence_record)
    return evidence_record


async def analyze_application_evidence(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> Sequence[Evidence]:
    application = await _get_tenant_application(session, application_id, organization_id)

    if not application.resume_text or not application.resume_text.strip():
        raise NoProcessedResumeError("No processed resume text found for this application")

    job_stmt = select(Job).where(Job.id == application.job_id)
    job = await session.scalar(job_stmt)
    if job is None:
        raise ApplicationNotFoundError("Job not found")

    caps_stmt = select(Capability).where(Capability.job_id == application.job_id)
    capabilities = (await session.scalars(caps_stmt)).all()
    if not capabilities:
        raise NoApprovedCapabilitiesError("Job has no approved capabilities to analyze")

    cap_map = {c.name.strip().lower(): c for c in capabilities}
    cap_payload = [
        {"name": c.name, "description": c.description} for c in capabilities
    ]

    ai_items = await extract_evidence_from_resume(
        job_title=job.title,
        job_description=job.description,
        capabilities=cap_payload,
        resume_text=application.resume_text,
    )

    for item in ai_items:
        norm_name = item.capability_name.strip().lower()
        if norm_name not in cap_map:
            continue

        target_cap = cap_map[norm_name]
        if target_cap.job_id != application.job_id:
            continue

        strength_str = item.strength.value if hasattr(item.strength, "value") else str(item.strength)
        content_val = None if strength_str == "INSUFFICIENT" else item.evidence

        ev_stmt = select(Evidence).where(
            Evidence.application_id == application.id,
            Evidence.capability_id == target_cap.id,
            Evidence.source_type == "RESUME",
        )
        existing_ev = await session.scalar(ev_stmt)

        if existing_ev is not None:
            existing_ev.strength = strength_str
            existing_ev.provenance = "CLAIM"
            existing_ev.content = content_val
            existing_ev.candidate_source_id = None
            existing_ev.updated_at = datetime.utcnow()
        else:
            new_ev = Evidence(
                application_id=application.id,
                capability_id=target_cap.id,
                candidate_source_id=None,
                source_type="RESUME",
                strength=strength_str,
                provenance="CLAIM",
                content=content_val,
            )
            session.add(new_ev)

    await session.commit()

    result_stmt = (
        select(Evidence)
        .where(
            Evidence.application_id == application.id,
            Evidence.source_type == "RESUME",
        )
        .order_by(Evidence.created_at.asc())
    )
    results = await session.scalars(result_stmt)
    return results.all()


async def get_application_evidence_summary(
    session: AsyncSession,
    application_id: Union[UUID, str],
    organization_id: Union[UUID, str],
) -> ApplicationEvidenceSummary:
    app_uuid = UUID(str(application_id)) if not isinstance(application_id, UUID) else application_id
    org_uuid = UUID(str(organization_id)) if not isinstance(organization_id, UUID) else organization_id
    application = await _get_tenant_application(session, app_uuid, org_uuid)

    caps_stmt = (
        select(Capability)
        .where(Capability.job_id == application.job_id)
        .order_by(Capability.created_at.asc())
    )
    capabilities = (await session.scalars(caps_stmt)).all()

    ev_stmt = select(Evidence).where(
        Evidence.application_id == application.id,
    ).order_by(Evidence.updated_at.desc())
    evidence_records = (await session.scalars(ev_stmt)).all()

    # Map capability_id to the most relevant/recent evidence record
    evidence_map: dict[UUID, Evidence] = {}
    for ev in evidence_records:
        if ev.capability_id not in evidence_map:
            evidence_map[ev.capability_id] = ev
        else:
            # Prefer demonstrated/verified provenance or non-insufficient strength if existing is claim/insufficient
            existing = evidence_map[ev.capability_id]
            if existing.strength == "INSUFFICIENT" and ev.strength != "INSUFFICIENT":
                evidence_map[ev.capability_id] = ev

    cap_summaries: list[CapabilityEvidenceSummary] = []
    for cap in capabilities:
        ev = evidence_map.get(cap.id)
        if ev is not None:
            state = CapabilityEvidenceState.KNOWN
            strength = EvidenceStrength(ev.strength)
            prov_str = getattr(ev, "provenance", "CLAIM") or "CLAIM"
            provenance = EvidenceProvenance(prov_str)
            content = ev.content
            cand_src_id = ev.candidate_source_id
        else:
            state = CapabilityEvidenceState.UNKNOWN
            strength = EvidenceStrength.INSUFFICIENT
            provenance = EvidenceProvenance.CLAIM
            content = None
            cand_src_id = None

        cap_summaries.append(
            CapabilityEvidenceSummary(
                capability_id=cap.id,
                name=cap.name,
                state=state,
                strength=strength,
                provenance=provenance,
                evidence=content,
                candidate_source_id=cand_src_id,
                source_id=cand_src_id,
            )
        )

    return ApplicationEvidenceSummary(
        application_id=application.id,
        capabilities=cap_summaries,
    )
