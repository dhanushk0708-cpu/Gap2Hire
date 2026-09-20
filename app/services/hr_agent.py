import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.hr_agent import (
    Citation,
    CitationType,
    HRAgentResponse,
    VerificationRecommendation,
)
from app.services.ai_hr_agent import HRAgentServiceError, run_hr_agent_reasoning
from app.services.application import ApplicationNotFoundError

logger = logging.getLogger(__name__)


async def process_hr_agent_request(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    message: str,
) -> HRAgentResponse:
    # 1. Authorize application and organization tenant isolation
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

    # 2. Retrieve Job
    job_stmt = select(Job).where(Job.id == application.job_id)
    job = await session.scalar(job_stmt)
    if job is None:
        raise ApplicationNotFoundError("Job not found")

    # 3. Retrieve capabilities for job
    caps_stmt = (
        select(Capability)
        .where(Capability.job_id == application.job_id)
        .order_by(Capability.created_at.asc())
    )
    capabilities = (await session.scalars(caps_stmt)).all()
    valid_cap_ids = {c.id for c in capabilities}

    # 4. Retrieve evidence
    ev_stmt = select(Evidence).where(
        Evidence.application_id == application.id,
        Evidence.source_type == "RESUME",
    )
    evidence_records = (await session.scalars(ev_stmt)).all()
    evidence_map = {ev.capability_id: ev for ev in evidence_records}

    # 5. Build gap summary
    gap_summary: list[dict[str, Any]] = []
    for cap in capabilities:
        ev = evidence_map.get(cap.id)
        if ev is not None:
            gap_summary.append({
                "capability_id": str(cap.id),
                "name": cap.name,
                "state": "KNOWN",
                "strength": ev.strength,
                "evidence": ev.content,
            })
        else:
            gap_summary.append({
                "capability_id": str(cap.id),
                "name": cap.name,
                "state": "UNKNOWN",
                "strength": "INSUFFICIENT",
                "evidence": None,
            })

    # 6. Retrieve existing verifications
    verif_stmt = (
        select(Verification)
        .where(Verification.application_id == application.id)
        .order_by(Verification.created_at.desc())
    )
    existing_verifications = (await session.scalars(verif_stmt)).all()

    # 7. Format structured context for LLM reasoning
    job_info = {
        "title": job.title,
        "description": job.description,
    }
    cap_payload = [
        {"id": str(c.id), "name": c.name, "description": c.description, "importance": c.importance}
        for c in capabilities
    ]
    ev_payload = [
        {
            "id": str(e.id),
            "capability_id": str(e.capability_id),
            "source_type": e.source_type,
            "strength": e.strength,
            "content": e.content,
        }
        for e in evidence_records
    ]
    verif_payload = [
        {
            "id": str(v.id),
            "capability_id": str(v.capability_id),
            "type": v.type,
            "status": v.status,
            "instructions": v.instructions,
            "result": v.result,
        }
        for v in existing_verifications
    ]

    # 8. Run AI reasoning over authoritative server context
    ai_payload = await run_hr_agent_reasoning(
        job_info=job_info,
        capabilities=cap_payload,
        gap_summary=gap_summary,
        evidence_items=ev_payload,
        existing_verifications=verif_payload,
        hr_message=message,
    )

    # 9. Validate citations and recommendation against server truth
    validated_citations: list[Citation] = []
    for raw_citation in ai_payload.citations:
        try:
            cit = Citation.model_validate(raw_citation)
            validated_citations.append(cit)
        except Exception:
            logger.warning(f"Discarding invalid citation from AI: {raw_citation}")

    validated_rec: VerificationRecommendation | None = None
    if ai_payload.recommendation:
        try:
            rec = VerificationRecommendation.model_validate(ai_payload.recommendation)
            # Ensure recommended capability_id actually belongs to this application's job
            if rec.capability_id in valid_cap_ids:
                validated_rec = rec
            else:
                logger.warning(
                    f"Discarding AI recommendation with invalid capability_id {rec.capability_id}"
                )
        except Exception as exc:
            logger.warning(f"Discarding invalid recommendation from AI: {exc}")

    return HRAgentResponse(
        message=ai_payload.message,
        citations=validated_citations,
        recommendation=validated_rec,
    )
