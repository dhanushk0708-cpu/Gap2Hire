"""
Persistent Vector Embedding Storage & Synchronization Foundation for Feature 4 RAG.

Manages idempotent persistence, content change detection (SHA-256), stale chunk
reconciliation, and tenant/scope isolation in the `rag_embeddings` table.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.job import Job
from app.models.rag_embedding import RagEmbedding
from app.services.embedding_service import (
    EmbeddingProvider,
    EmbeddingServiceError,
    MockEmbeddingProvider,
    get_embedding_provider,
    validate_embedding_vector,
)

logger = logging.getLogger(__name__)


class EmbeddingSyncError(Exception):
    """Raised when synchronization, scope consistency, or transaction validation fails."""


@dataclass
class SyncItem:
    """A structured chunk ready for persistent vector storage."""
    chunk_id: str
    source_type: str
    text: str
    source_id: Optional[UUID] = None
    application_id: Optional[UUID] = None
    job_id: Optional[UUID] = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    """Summary of operations performed during synchronization."""
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    total_processed: int = 0


def compute_content_hash(text: str) -> str:
    """Computes a deterministic SHA-256 hash of normalized chunk text."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def _validate_item_scopes(
    session: AsyncSession,
    organization_id: UUID,
    items: Sequence[SyncItem],
) -> None:
    """
    Authoritative scope consistency gate.
    
    Verifies that:
    1. Any job_id referenced belongs to organization_id.
    2. Any application_id referenced belongs to organization_id (via its job).
    3. If an item specifies both application_id and job_id, the application must
       belong to that specific job.
    """
    referenced_job_ids = {item.job_id for item in items if item.job_id is not None}
    referenced_app_ids = {item.application_id for item in items if item.application_id is not None}

    # 1. Verify job ownership
    if referenced_job_ids:
        job_stmt = (
            select(Job.id)
            .where(
                Job.id.in_(referenced_job_ids),
                Job.organization_id == organization_id,
            )
        )
        valid_job_ids = set((await session.execute(job_stmt)).scalars().all())
        invalid_jobs = referenced_job_ids - valid_job_ids
        if invalid_jobs:
            raise EmbeddingSyncError(
                f"Scope violation: Job(s) {invalid_jobs} do not exist or belong to another organization."
            )

    # 2. Verify application ownership and job alignment
    if referenced_app_ids:
        app_stmt = (
            select(Application.id, Application.job_id)
            .join(Job, Job.id == Application.job_id)
            .where(
                Application.id.in_(referenced_app_ids),
                Job.organization_id == organization_id,
            )
        )
        app_rows = (await session.execute(app_stmt)).all()
        valid_app_map: dict[UUID, UUID] = {row[0]: row[1] for row in app_rows}
        invalid_apps = referenced_app_ids - set(valid_app_map.keys())
        if invalid_apps:
            raise EmbeddingSyncError(
                f"Scope violation: Application(s) {invalid_apps} do not exist or belong to another organization."
            )

        # Check job_id conflict if both are present in the item
        for item in items:
            if item.application_id is not None and item.job_id is not None:
                actual_job_id = valid_app_map.get(item.application_id)
                if actual_job_id != item.job_id:
                    raise EmbeddingSyncError(
                        f"Scope conflict for chunk '{item.chunk_id}': Application {item.application_id} "
                        f"belongs to Job {actual_job_id}, but chunk metadata specified Job {item.job_id}."
                    )


async def sync_embeddings(
    session: AsyncSession,
    organization_id: UUID,
    items: Sequence[SyncItem],
    provider: Optional[EmbeddingProvider] = None,
    allow_mock: bool = False,
) -> SyncResult:
    """
    Idempotently synchronizes a list of chunks into the `rag_embeddings` table.

    Rules:
    - Tenant and scope isolation: Validates all referenced jobs and applications
      against authoritative business records for organization_id before writing.
    - Change detection: If `content_hash` and `embedding_model` match the existing row,
      re-embedding is skipped.
    - Updates: If `content_hash` or `embedding_model` differs, new embeddings are generated
      and the record is updated in place.
    - Insertions: New chunks are embedded and inserted.
    - Safety: If `allow_mock=False`, passing a MockEmbeddingProvider raises EmbeddingSyncError.
    - Transactional: Flushes changes into the session; errors raise and leave transaction
      to be rolled back by the caller.
    """
    if not items:
        return SyncResult()

    active_provider = provider or get_embedding_provider()

    # Guard: prevent mock embeddings from entering production storage unless explicitly allowed (tests)
    if not allow_mock and isinstance(active_provider, MockEmbeddingProvider):
        raise EmbeddingSyncError(
            "MockEmbeddingProvider output cannot be persisted when allow_mock=False. "
            "Configure a real embedding provider for production operations."
        )

    # Validate all referenced scopes against authoritative database records
    await _validate_item_scopes(session, organization_id, items)

    # 1. Fetch existing embedding rows for this tenant and chunk_ids
    chunk_ids = [item.chunk_id for item in items]
    stmt = (
        select(RagEmbedding)
        .where(
            RagEmbedding.organization_id == organization_id,
            RagEmbedding.chunk_id.in_(chunk_ids),
        )
    )
    result = await session.execute(stmt)
    existing_map: dict[str, RagEmbedding] = {r.chunk_id: r for r in result.scalars().all()}

    sync_result = SyncResult(total_processed=len(items))
    to_embed: list[tuple[SyncItem, Optional[RagEmbedding], str]] = []

    # 2. Check hashes and separate unchanged items from items needing embedding
    for item in items:
        content_hash = compute_content_hash(item.text)
        existing = existing_map.get(item.chunk_id)

        if existing is not None:
            # Check if content and model are identical
            if existing.content_hash == content_hash and existing.embedding_model == active_provider.model_name:
                sync_result.unchanged += 1
                continue
            # Content or model changed -> queue for update
            to_embed.append((item, existing, content_hash))
        else:
            # New chunk -> queue for insertion
            to_embed.append((item, None, content_hash))

    if not to_embed:
        return sync_result

    # 3. Generate embeddings for changed/new items
    for item, existing, content_hash in to_embed:
        try:
            raw_vec = active_provider.embed_text(item.text)
            validated_vec = validate_embedding_vector(raw_vec, active_provider.dimension)
        except EmbeddingServiceError as exc:
            logger.error("Embedding generation failed for chunk %s: %s", item.chunk_id, exc)
            raise EmbeddingSyncError(f"Embedding generation failed for chunk {item.chunk_id}: {exc}") from exc

        if existing is not None:
            # Update existing row
            existing.chunk_text = item.text
            existing.content_hash = content_hash
            existing.embedding = validated_vec
            existing.embedding_model = active_provider.model_name
            existing.source_type = item.source_type
            existing.source_id = item.source_id
            existing.application_id = item.application_id
            existing.job_id = item.job_id
            existing.metadata_json = item.metadata_json
            existing.updated_at = datetime.utcnow()
            sync_result.updated += 1
        else:
            # Insert new row
            new_row = RagEmbedding(
                organization_id=organization_id,
                chunk_id=item.chunk_id,
                source_type=item.source_type,
                source_id=item.source_id,
                application_id=item.application_id,
                job_id=item.job_id,
                chunk_text=item.text,
                content_hash=content_hash,
                embedding=validated_vec,
                embedding_model=active_provider.model_name,
                metadata_json=item.metadata_json,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(new_row)
            sync_result.created += 1

    # Flush changes to the database within caller's transaction
    await session.flush()
    return sync_result


async def reconcile_stale_chunks(
    session: AsyncSession,
    organization_id: UUID,
    active_chunk_ids: set[str],
    application_id: Optional[UUID] = None,
    job_id: Optional[UUID] = None,
) -> int:
    """
    Removes indexed chunks that are no longer present in the authoritative source records.

    Scope:
    - If `application_id` is supplied: validates that the application belongs to organization_id,
      then reconciles only chunks belonging to that application.
    - If `job_id` is supplied: validates that the job belongs to organization_id,
      then reconciles only chunks belonging to that job.
    - If neither: reconciles across the entire organization.
    Returns the number of deleted stale chunks.
    """
    # Authoritative scope validation for reconciliation
    if application_id is not None:
        app_stmt = (
            select(Application.id)
            .join(Job, Job.id == Application.job_id)
            .where(
                Application.id == application_id,
                Job.organization_id == organization_id,
            )
        )
        if job_id is not None:
            app_stmt = app_stmt.where(Application.job_id == job_id)

        app_res = await session.execute(app_stmt)
        if not app_res.scalar():
            raise EmbeddingSyncError(
                f"Reconciliation scope violation: Application {application_id} "
                f"does not belong to organization {organization_id} (or job {job_id})."
            )
    elif job_id is not None:
        job_stmt = select(Job.id).where(
            Job.id == job_id,
            Job.organization_id == organization_id,
        )
        job_res = await session.execute(job_stmt)
        if not job_res.scalar():
            raise EmbeddingSyncError(
                f"Reconciliation scope violation: Job {job_id} does not belong to organization {organization_id}."
            )

    stmt = delete(RagEmbedding).where(RagEmbedding.organization_id == organization_id)

    if application_id is not None:
        stmt = stmt.where(RagEmbedding.application_id == application_id)
    elif job_id is not None:
        stmt = stmt.where(RagEmbedding.job_id == job_id)

    if active_chunk_ids:
        stmt = stmt.where(RagEmbedding.chunk_id.not_in(active_chunk_ids))

    result = await session.execute(stmt)
    await session.flush()
    deleted_count = result.rowcount or 0
    return deleted_count
