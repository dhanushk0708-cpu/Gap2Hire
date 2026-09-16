from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.job import Job
from app.schemas.evidence import (
    ApplicationEvidenceSummary,
    CapabilityEvidenceState,
    CapabilityEvidenceSummary,
    EvidenceStrength,
)
from app.services.ai_evidence import extract_evidence_from_resume
from app.services.application import ApplicationNotFoundError


class NoProcessedResumeError(Exception):
    pass


class NoApprovedCapabilitiesError(Exception):
    pass


async def analyze_application_evidence(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> Sequence[Evidence]:
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
            existing_ev.content = content_val
            existing_ev.updated_at = datetime.utcnow()
        else:
            new_ev = Evidence(
                application_id=application.id,
                capability_id=target_cap.id,
                source_type="RESUME",
                strength=strength_str,
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
    application_id: UUID,
    organization_id: UUID,
) -> ApplicationEvidenceSummary:
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

    caps_stmt = (
        select(Capability)
        .where(Capability.job_id == application.job_id)
        .order_by(Capability.created_at.asc())
    )
    capabilities = (await session.scalars(caps_stmt)).all()

    ev_stmt = select(Evidence).where(
        Evidence.application_id == application.id,
        Evidence.source_type == "RESUME",
    )
    evidence_records = (await session.scalars(ev_stmt)).all()

    evidence_map = {ev.capability_id: ev for ev in evidence_records}

    cap_summaries: list[CapabilityEvidenceSummary] = []
    for cap in capabilities:
        ev = evidence_map.get(cap.id)
        if ev is not None:
            state = CapabilityEvidenceState.KNOWN
            strength = EvidenceStrength(ev.strength)
            content = ev.content
        else:
            state = CapabilityEvidenceState.UNKNOWN
            strength = EvidenceStrength.INSUFFICIENT
            content = None

        cap_summaries.append(
            CapabilityEvidenceSummary(
                capability_id=cap.id,
                name=cap.name,
                state=state,
                strength=strength,
                evidence=content,
            )
        )

    return ApplicationEvidenceSummary(
        application_id=application.id,
        capabilities=cap_summaries,
    )
