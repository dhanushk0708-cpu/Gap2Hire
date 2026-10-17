"""
Feature 4: Hiring Intelligence Chat API.

Single POST endpoint:  POST /api/v1/hiring-intelligence/chat

Authentication: Bearer JWT (application_manager role).
Tenant isolation: enforced via current_user.organization_id.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.hiring_chat import (
    HiringChatRequest,
    HiringChatResponse,
    IndexSyncResponse,
)
from app.services.hiring_chat import HiringChatServiceError, run_hiring_chat
from app.services.rag_indexer import sync_tenant_rag_index

router = APIRouter(
    prefix="/api/v1/hiring-intelligence",
    tags=["Hiring Intelligence Chat"],
)

_require_manager = require_roles("HR_MANAGER", "ADMIN", "application_manager")


@router.post(
    "/chat",
    response_model=HiringChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a hiring-intelligence question (RAG + LLM)",
    description=(
        "Retrieve evidence-grounded context from the database and generate an advisory "
        "AI answer.  Optionally scope retrieval to a specific application or job. "
        "All responses are advisory-only and never modify any hiring record."
    ),
)
async def hiring_intelligence_chat(
    body: HiringChatRequest,
    current_user: User = Depends(_require_manager),
    session: AsyncSession = Depends(get_db_session),
) -> HiringChatResponse:
    """
    POST /api/v1/hiring-intelligence/chat

    Accepts a user message and optional conversation history, retrieves relevant
    context chunks from the tenant database, and returns an LLM-generated advisory
    answer with provenance citations.
    """
    try:
        return await run_hiring_chat(
            session=session,
            request=body,
            current_user=current_user,
        )
    except HiringChatServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/sync-index",
    response_model=IndexSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Synchronize tenant RAG vector index",
    description=(
        "Explicitly refreshes vector embeddings for the authenticated tenant idempotently. "
        "Re-indexes changed/new chunks and reconciles stale chunks within tenant scope."
    ),
)
async def sync_tenant_rag_index_endpoint(
    job_id: Optional[UUID] = Query(None, description="Optional job scope"),
    application_id: Optional[UUID] = Query(None, description="Optional application scope"),
    current_user: User = Depends(_require_manager),
    session: AsyncSession = Depends(get_db_session),
) -> IndexSyncResponse:
    """
    POST /api/v1/hiring-intelligence/sync-index

    Enables explicit index refresh so that newly added candidate profiles, evidence,
    job descriptions, or outcome logs become searchable via hybrid retrieval.
    """
    try:
        sync_res = await sync_tenant_rag_index(
            session=session,
            organization_id=current_user.organization_id,
            application_id=application_id,
            job_id=job_id,
            reconcile=True,
        )
        await session.commit()
        return IndexSyncResponse(
            status="ok",
            organization_id=current_user.organization_id,
            created=sync_res.created,
            updated=sync_res.updated,
            unchanged=sync_res.unchanged,
            total_processed=sync_res.total_processed,
            synced_at=datetime.utcnow(),
        )
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index synchronization failed: {exc}",
        ) from exc

