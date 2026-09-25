from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate_source import CandidateSource
from app.models.job import Job
from app.schemas.candidate_source import (
    CandidateSourceCreate,
    CandidateSourceUpdate,
)


class ApplicationNotFoundError(Exception):
    pass


class CandidateSourceNotFoundError(Exception):
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
        raise ApplicationNotFoundError(f"Application {application_id} not found")
    return application


async def create_candidate_source(
    session: AsyncSession,
    organization_id: UUID,
    application_id: UUID,
    data: CandidateSourceCreate,
) -> CandidateSource:
    """Creates a new candidate source record attached to an application under tenant isolation."""
    await _get_tenant_application(session, application_id, organization_id)

    source = CandidateSource(
        application_id=application_id,
        url=data.url,
        source_type=data.source_type,
        discovered_from=data.discovered_from,
        discovery_depth=data.discovery_depth,
        status=data.status,
        relevance=data.relevance,
        title=data.title,
        metadata_=data.metadata,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def list_candidate_sources(
    session: AsyncSession,
    organization_id: UUID,
    application_id: UUID,
) -> Sequence[CandidateSource]:
    """Lists all candidate sources for an application under tenant isolation."""
    await _get_tenant_application(session, application_id, organization_id)

    stmt = (
        select(CandidateSource)
        .where(CandidateSource.application_id == application_id)
        .order_by(CandidateSource.discovery_depth.asc(), CandidateSource.created_at.asc())
    )
    return (await session.scalars(stmt)).all()


async def get_candidate_source(
    session: AsyncSession,
    organization_id: UUID,
    source_id: UUID,
) -> CandidateSource:
    """Retrieves a single candidate source by ID with tenant isolation verification."""
    stmt = (
        select(CandidateSource)
        .join(Application, Application.id == CandidateSource.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            CandidateSource.id == source_id,
            Job.organization_id == organization_id,
        )
    )
    source = await session.scalar(stmt)
    if source is None:
        raise CandidateSourceNotFoundError(f"Candidate source {source_id} not found")
    return source


async def update_candidate_source(
    session: AsyncSession,
    organization_id: UUID,
    source_id: UUID,
    data: CandidateSourceUpdate,
) -> CandidateSource:
    """Updates fields on an existing candidate source with tenant isolation."""
    source = await get_candidate_source(session, organization_id, source_id)

    update_dict = data.model_dump(exclude_unset=True)
    if "url" in update_dict and update_dict["url"] is not None:
        source.url = update_dict["url"]
    if "source_type" in update_dict and update_dict["source_type"] is not None:
        source.source_type = update_dict["source_type"]
    if "discovered_from" in update_dict:
        source.discovered_from = update_dict["discovered_from"]
    if "discovery_depth" in update_dict and update_dict["discovery_depth"] is not None:
        source.discovery_depth = update_dict["discovery_depth"]
    if "status" in update_dict and update_dict["status"] is not None:
        source.status = update_dict["status"]
    if "relevance" in update_dict:
        source.relevance = update_dict["relevance"]
    if "title" in update_dict:
        source.title = update_dict["title"]
    if "metadata" in update_dict:
        source.metadata_ = update_dict["metadata"]
    if "last_inspected_at" in update_dict:
        source.last_inspected_at = update_dict["last_inspected_at"]

    source.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(source)
    return source


async def mark_source_inspected(
    session: AsyncSession,
    organization_id: UUID,
    source_id: UUID,
    relevance: str | None = None,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CandidateSource:
    """Marks a candidate source as INSPECTED and sets last_inspected_at timestamp."""
    source = await get_candidate_source(session, organization_id, source_id)
    source.status = "INSPECTED"
    source.last_inspected_at = datetime.utcnow()
    if relevance is not None:
        source.relevance = relevance
    if title is not None:
        source.title = title
    if metadata is not None:
        source.metadata_ = metadata

    source.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(source)
    return source


async def register_discovered_sources(
    session: AsyncSession,
    organization_id: UUID,
    application_id: UUID,
    discovered_links: Sequence[Any],
) -> list[CandidateSource]:
    """
    Registers a collection of discovered links as CandidateSource records attached
    to an application under tenant isolation.
    Performs application-level deduplication to avoid creating duplicate sources.
    """
    await _get_tenant_application(session, application_id, organization_id)

    if not discovered_links:
        return []

    # Fetch all existing URLs registered for this application
    existing_urls_stmt = select(CandidateSource.url).where(
        CandidateSource.application_id == application_id
    )
    existing_urls_result = await session.scalars(existing_urls_stmt)
    existing_urls = set(existing_urls_result.all())

    new_sources: list[CandidateSource] = []
    seen_in_batch: set[str] = set()

    for link in discovered_links:
        link_url = getattr(link, "url", None) or (link.get("url") if isinstance(link, dict) else None)
        if not link_url or link_url in existing_urls or link_url in seen_in_batch:
            continue

        seen_in_batch.add(link_url)

        source_type = getattr(link, "source_type", "OTHER") if not isinstance(link, dict) else link.get("source_type", "OTHER")
        discovered_from = getattr(link, "discovered_from", None) if not isinstance(link, dict) else link.get("discovered_from")
        discovery_depth = getattr(link, "discovery_depth", 1) if not isinstance(link, dict) else link.get("discovery_depth", 1)
        anchor_text = getattr(link, "anchor_text", None) if not isinstance(link, dict) else link.get("anchor_text")
        source_url = getattr(link, "source_url", None) if not isinstance(link, dict) else link.get("source_url")

        source = CandidateSource(
            application_id=application_id,
            url=link_url,
            source_type=source_type,
            discovered_from=discovered_from,
            discovery_depth=discovery_depth,
            status="DISCOVERED",
            title=anchor_text,
            metadata_={"discovered_from_source": source_url} if source_url else None,
        )
        session.add(source)
        new_sources.append(source)

    if new_sources:
        await session.commit()
        for src in new_sources:
            await session.refresh(src)

    return new_sources
