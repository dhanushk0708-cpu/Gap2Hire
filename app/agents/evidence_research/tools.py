import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.candidate_source import CandidateSource
from app.services.candidate_sources import (
    CandidateSourceNotFoundError,
    get_candidate_source,
    register_discovered_sources,
)
from app.services.link_discovery import LinkDiscovery
from app.services.source_inspection import SourceInspector

logger = logging.getLogger(__name__)


async def inspect_candidate_source_impl(
    source_id: str,
    organization_id: str,
    application_id: str,
    session: Optional[AsyncSession] = None,
) -> dict[str, Any]:
    """
    Deterministic implementation that safely inspects a registered CandidateSource URL
    using the Step 2 SourceInspector with SSRF protection, limits, and timeouts.
    """
    src_uuid = UUID(source_id)
    org_uuid = UUID(organization_id)
    app_uuid = UUID(application_id)

    own_session = False
    if session is None:
        session = async_session_factory()
        own_session = True

    try:
        try:
            source = await get_candidate_source(session, org_uuid, src_uuid)
        except CandidateSourceNotFoundError as e:
            return {
                "source_id": source_id,
                "is_success": False,
                "error": str(e),
            }

        if source.application_id != app_uuid:
            return {
                "source_id": source_id,
                "is_success": False,
                "error": f"Candidate source {source_id} belongs to a different application",
            }

        # Safe HTTP/HTTPS inspection
        inspector = SourceInspector()
        result = await inspector.inspect(source.url)

        extracted_text = result.extracted_text or ""

        # For GitHub / code repositories, also discover and inspect high-signal artifacts (README, pyproject, requirements, etc.)
        if result.is_success and source.source_type.upper() in {"GITHUB", "GITLAB"} and not source.url.endswith((".py", ".toml", ".txt", ".json", ".md")):
            try:
                from app.services.source_artifact_discovery import deep_inspect_candidate_source
                deep_res = await deep_inspect_candidate_source(
                    url=source.url,
                    source_type=source.source_type,
                    inspector=inspector,
                )
                if deep_res.get("successful_artifacts", 0) > 0 and deep_res.get("combined_artifact_text"):
                    extracted_text = (extracted_text + "\n\n" + deep_res["combined_artifact_text"]).strip()
            except Exception as deep_err:
                logger.info(f"Deep artifact inspection notice for {source.url}: {deep_err}")

        # Update candidate source inspection status
        if result.is_success:
            source.status = "INSPECTED"
            source.last_inspected_at = datetime.utcnow()
            if result.title:
                source.title = result.title
            await session.commit()
        else:
            source.status = "FAILED"
            source.last_inspected_at = datetime.utcnow()
            await session.commit()

        return {
            "source_id": str(source.id),
            "url": source.url,
            "source_type": source.source_type,
            "is_success": result.is_success,
            "http_status": result.http_status,
            "title": result.title,
            "extracted_text": extracted_text,
            "content_length": len(extracted_text.encode("utf-8")),
            "error": result.error_message,
        }
    finally:
        if own_session:
            await session.close()


async def discover_candidate_links_impl(
    source_id: str,
    organization_id: str,
    application_id: str,
    html_content: str,
    session: Optional[AsyncSession] = None,
) -> dict[str, Any]:
    """
    Deterministic implementation that extracts and registers candidate links from HTML
    using the Step 3 LinkDiscovery service under tenant isolation.
    """
    src_uuid = UUID(source_id)
    org_uuid = UUID(organization_id)
    app_uuid = UUID(application_id)

    own_session = False
    if session is None:
        session = async_session_factory()
        own_session = True

    try:
        try:
            source = await get_candidate_source(session, org_uuid, src_uuid)
        except CandidateSourceNotFoundError as e:
            return {
                "source_id": source_id,
                "new_sources_registered": 0,
                "error": str(e),
            }

        if source.application_id != app_uuid:
            return {
                "source_id": source_id,
                "new_sources_registered": 0,
                "error": f"Candidate source {source_id} belongs to a different application",
            }

        discovery = LinkDiscovery()
        discovered_links = discovery.discover_links(
            page_url=source.url,
            html_content=html_content,
            current_depth=source.discovery_depth,
        )

        created_sources = await register_discovered_sources(
            session=session,
            organization_id=org_uuid,
            application_id=app_uuid,
            discovered_links=discovered_links,
        )

        return {
            "source_id": str(source.id),
            "new_sources_registered": len(created_sources),
            "discovered_sources": [
                {
                    "id": str(s.id),
                    "url": s.url,
                    "source_type": s.source_type,
                    "title": s.title,
                    "discovery_depth": s.discovery_depth,
                }
                for s in created_sources
            ],
        }
    finally:
        if own_session:
            await session.close()


@tool("inspect_candidate_source")
async def inspect_candidate_source_tool(
    source_id: str,
    organization_id: str,
    application_id: str,
) -> dict[str, Any]:
    """
    Inspects a registered candidate source URL safely and returns the page title,
    status, and extracted textual content.
    """
    return await inspect_candidate_source_impl(
        source_id=source_id,
        organization_id=organization_id,
        application_id=application_id,
    )


@tool("discover_candidate_links")
async def discover_candidate_links_tool(
    source_id: str,
    organization_id: str,
    application_id: str,
    html_content: str,
) -> dict[str, Any]:
    """
    Discovers new relevant candidate links within the HTML content of an inspected source
    and registers them as CandidateSource records.
    """
    return await discover_candidate_links_impl(
        source_id=source_id,
        organization_id=organization_id,
        application_id=application_id,
        html_content=html_content,
    )
