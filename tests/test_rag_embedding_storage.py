"""
Tests for Stage 2: Persistent Vector Embedding Storage & Synchronization.

Separated into:
1. Unit tests: Verify hashing, contracts, mock protection, and failure handling without DB.
2. Integration tests: Verify PostgreSQL persistence, pgvector similarity queries, uniqueness,
   change detection, tenant isolation, and stale chunk reconciliation against local PostgreSQL.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import async_session_factory
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.organization import Organization
from app.models.rag_embedding import RagEmbedding
from app.models.user import User
from app.services.embedding_service import (
    EmbeddingServiceError,
    MockEmbeddingProvider,
)
from app.services.rag_embedding_storage import (
    EmbeddingSyncError,
    SyncItem,
    SyncResult,
    compute_content_hash,
    reconcile_stale_chunks,
    sync_embeddings,
)


# ===========================================================================
# 1. Unit Tests (No Database)
# ===========================================================================

class TestUnitEmbeddingStorage:
    def test_content_hash_stability(self):
        h1 = compute_content_hash("Senior Python Developer with FastAPI")
        h2 = compute_content_hash("Senior Python Developer with FastAPI")
        assert h1 == h2
        assert len(h1) == 64

    def test_content_hash_normalizes_whitespace(self):
        h1 = compute_content_hash("Candidate: Alice | Job: Developer")
        h2 = compute_content_hash("  Candidate:  Alice   | \n Job: Developer \t")
        assert h1 == h2

    def test_content_hash_different_text_produces_different_hash(self):
        h1 = compute_content_hash("Text A")
        h2 = compute_content_hash("Text B")
        assert h1 != h2

    @pytest.mark.asyncio
    async def test_empty_items_returns_zero_counts(self):
        mock_session = MagicMock()
        res = await sync_embeddings(
            session=mock_session,
            organization_id=uuid.uuid4(),
            items=[],
            allow_mock=True,
        )
        assert res.total_processed == 0
        assert res.created == 0
        assert res.updated == 0
        assert res.unchanged == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_mock_guard_raises_in_production_mode(self):
        mock_session = MagicMock()
        mock_provider = MockEmbeddingProvider()
        item = SyncItem(chunk_id="test-1", source_type="EVIDENCE", text="Sample text")

        with pytest.raises(EmbeddingSyncError, match="MockEmbeddingProvider output cannot be persisted"):
            await sync_embeddings(
                session=mock_session,
                organization_id=uuid.uuid4(),
                items=[item],
                provider=mock_provider,
                allow_mock=False,  # Production mode
            )

    @pytest.mark.asyncio
    async def test_embedding_failure_aborts_sync(self):
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        faulty_provider = MagicMock()
        faulty_provider.model_name = "faulty-model"
        faulty_provider.dimension = 384
        faulty_provider.embed_text.side_effect = EmbeddingServiceError("Inference failed")

        item = SyncItem(chunk_id="chunk-1", source_type="EVIDENCE", text="Sample evidence")
        with pytest.raises(EmbeddingSyncError, match="Embedding generation failed"):
            await sync_embeddings(
                session=mock_session,
                organization_id=uuid.uuid4(),
                items=[item],
                provider=faulty_provider,
                allow_mock=True,
            )


# ===========================================================================
# 2. Integration Tests (Local PostgreSQL + pgvector)
# ===========================================================================

@asynccontextmanager
async def create_test_org() -> AsyncGenerator[Organization, None]:
    """Helper context manager to create and cleanly remove an isolated test organization."""
    slug = f"org-{uuid.uuid4().hex[:12]}"
    async with async_session_factory() as session:
        org = Organization(
            name=f"Test Org Embeddings {uuid.uuid4().hex[:8]}",
            slug=slug,
        )
        session.add(org)
        await session.commit()
        await session.refresh(org)
        org_id = org.id

    try:
        yield org
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Job).where(Job.organization_id == org_id))
            existing = await session.get(Organization, org_id)
            if existing:
                await session.delete(existing)
                await session.commit()


async def _create_test_user_and_job(session, org_id: uuid.UUID) -> tuple[User, Job]:
    user = User(
        organization_id=org_id,
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="fake-hash",
        full_name="HR Manager",
        role="HR_MANAGER",
    )
    session.add(user)
    await session.flush()
    job = Job(
        organization_id=org_id,
        title=f"Test Job {uuid.uuid4().hex[:6]}",
        description="Job description for testing",
        created_by=user.id,
    )
    session.add(job)
    await session.flush()
    return user, job


@pytest.mark.asyncio
class TestIntegrationEmbeddingStorage:
    async def test_first_time_insertion_and_vector_query(self):
        async with create_test_org() as test_org:
            provider = MockEmbeddingProvider(dimension=384, model_name="mock-mini-lm-384")
            item1 = SyncItem(
                chunk_id="profile-app-1",
                source_type="CANDIDATE_PROFILE",
                text="Candidate Alice | Applied to: Python Developer | Experience in FastAPI and SQL",
            )
            item2 = SyncItem(
                chunk_id="ev-item-2",
                source_type="EVIDENCE",
                text="Evidence | Candidate: Alice | Capability: Problem Solving | Strong code samples",
            )

            async with async_session_factory() as session:
                result = await sync_embeddings(
                    session=session,
                    organization_id=test_org.id,
                    items=[item1, item2],
                    provider=provider,
                    allow_mock=True,
                )
                await session.commit()

            assert result.created == 2
            assert result.updated == 0
            assert result.unchanged == 0
            assert result.total_processed == 2

            # Verify rows in PostgreSQL using pgvector cosine distance operator <=>
            async with async_session_factory() as session:
                stmt = (
                    select(RagEmbedding)
                    .where(RagEmbedding.organization_id == test_org.id)
                    .order_by(RagEmbedding.chunk_id)
                )
                rows = (await session.execute(stmt)).scalars().all()
                assert len(rows) == 2
                assert rows[0].chunk_id == "ev-item-2"
                assert rows[1].chunk_id == "profile-app-1"
                assert len(rows[0].embedding) == 384
                assert len(rows[1].embedding) == 384

                # Verify pgvector cosine similarity calculation directly via SQL query
                q_vec = provider.embed_text("FastAPI and Python")
                vec_literal = f"[{','.join(str(x) for x in q_vec)}]"
                distance_stmt = text(
                    f"SELECT chunk_id, embedding <=> '{vec_literal}'::vector AS distance "
                    f"FROM rag_embeddings WHERE organization_id = :org_id "
                    f"ORDER BY distance ASC"
                )
                res = await session.execute(distance_stmt, {"org_id": test_org.id})
                query_rows = res.fetchall()
                assert len(query_rows) == 2
                assert query_rows[0][1] >= 0.0  # Cosine distance is >= 0

    async def test_unchanged_content_skips_embedding(self):
        async with create_test_org() as test_org:
            provider = MockEmbeddingProvider(dimension=384, model_name="mock-mini-lm-384")
            item = SyncItem(
                chunk_id="jd-job-1",
                source_type="JOB_DESCRIPTION",
                text="Job: Software Engineer | Requirements: Python, PostgreSQL, Docker",
            )

            # First sync: inserts item
            async with async_session_factory() as session:
                await sync_embeddings(
                    session=session,
                    organization_id=test_org.id,
                    items=[item],
                    provider=provider,
                    allow_mock=True,
                )
                await session.commit()

            # Spy provider to ensure embed_text is NOT called for unchanged content
            spy_provider = MagicMock(wraps=provider)
            spy_provider.model_name = provider.model_name
            spy_provider.dimension = provider.dimension

            async with async_session_factory() as session:
                res = await sync_embeddings(
                    session=session,
                    organization_id=test_org.id,
                    items=[item],
                    provider=spy_provider,
                    allow_mock=True,
                )
                await session.commit()

            assert res.unchanged == 1
            assert res.created == 0
            assert res.updated == 0
            # embed_text must NOT have been called because hash and model matched
            spy_provider.embed_text.assert_not_called()

    async def test_changed_content_updates_embedding(self):
        async with create_test_org() as test_org:
            provider = MockEmbeddingProvider(dimension=384, model_name="mock-mini-lm-384")
            item_v1 = SyncItem(
                chunk_id="outcome-1",
                source_type="POST_HIRE_OUTCOME",
                text="Post-Hire Outcome | Initial observation: Good onboarding progress",
            )

            async with async_session_factory() as session:
                await sync_embeddings(
                    session=session,
                    organization_id=test_org.id,
                    items=[item_v1],
                    provider=provider,
                    allow_mock=True,
                )
                await session.commit()

            # Update content for the same chunk_id
            item_v2 = SyncItem(
                chunk_id="outcome-1",
                source_type="POST_HIRE_OUTCOME",
                text="Post-Hire Outcome | Updated observation: Promoted to Tech Lead with exceptional velocity",
            )

            async with async_session_factory() as session:
                res = await sync_embeddings(
                    session=session,
                    organization_id=test_org.id,
                    items=[item_v2],
                    provider=provider,
                    allow_mock=True,
                )
                await session.commit()

            assert res.updated == 1
            assert res.created == 0
            assert res.unchanged == 0

            async with async_session_factory() as session:
                row = (
                    await session.execute(
                        select(RagEmbedding).where(
                            RagEmbedding.organization_id == test_org.id,
                            RagEmbedding.chunk_id == "outcome-1",
                        )
                    )
                ).scalar_one()
                assert "Promoted to Tech Lead" in row.chunk_text
                assert row.content_hash == compute_content_hash(item_v2.text)

    async def test_model_identifier_change_triggers_reembedding(self):
        async with create_test_org() as test_org:
            provider_v1 = MockEmbeddingProvider(dimension=384, model_name="model-v1")
            item = SyncItem(chunk_id="cap-1", source_type="JOB_DESCRIPTION", text="Capability: API Design")

            async with async_session_factory() as session:
                await sync_embeddings(
                    session=session,
                    organization_id=test_org.id,
                    items=[item],
                    provider=provider_v1,
                    allow_mock=True,
                )
                await session.commit()

            # Same text, but new provider model version
            provider_v2 = MockEmbeddingProvider(dimension=384, model_name="model-v2")
            async with async_session_factory() as session:
                res = await sync_embeddings(
                    session=session,
                    organization_id=test_org.id,
                    items=[item],
                    provider=provider_v2,
                    allow_mock=True,
                )
                await session.commit()

            assert res.updated == 1
            assert res.created == 0
            assert res.unchanged == 0

            async with async_session_factory() as session:
                row = (
                    await session.execute(
                        select(RagEmbedding).where(
                            RagEmbedding.organization_id == test_org.id,
                            RagEmbedding.chunk_id == "cap-1",
                        )
                    )
                ).scalar_one()
                assert row.embedding_model == "model-v2"

    async def test_unique_chunk_constraint_in_db(self):
        """Verifies PostgreSQL unique constraint uq_rag_embeddings_org_chunk prevents duplicate chunk_id."""
        async with create_test_org() as test_org:
            provider = MockEmbeddingProvider(dimension=384)
            vec = provider.embed_text("Sample text")

            async with async_session_factory() as session:
                row1 = RagEmbedding(
                    organization_id=test_org.id,
                    chunk_id="duplicate-chunk",
                    source_type="EVIDENCE",
                    chunk_text="First copy",
                    content_hash=compute_content_hash("First copy"),
                    embedding=vec,
                    embedding_model="mock-mini-lm-384",
                )
                session.add(row1)
                await session.commit()

            # Attempt to insert identical (organization_id, chunk_id)
            async with async_session_factory() as session:
                row2 = RagEmbedding(
                    organization_id=test_org.id,
                    chunk_id="duplicate-chunk",
                    source_type="EVIDENCE",
                    chunk_text="Second copy",
                    content_hash=compute_content_hash("Second copy"),
                    embedding=vec,
                    embedding_model="mock-mini-lm-384",
                )
                session.add(row2)
                with pytest.raises(IntegrityError):
                    await session.commit()

    async def test_repeated_synchronization_no_duplicates(self):
        async with create_test_org() as test_org:
            provider = MockEmbeddingProvider(dimension=384)
            items = [
                SyncItem(chunk_id=f"chunk-{i}", source_type="EVIDENCE", text=f"Evidence text {i}")
                for i in range(5)
            ]

            for _ in range(3):
                async with async_session_factory() as session:
                    await sync_embeddings(
                        session=session,
                        organization_id=test_org.id,
                        items=items,
                        provider=provider,
                        allow_mock=True,
                    )
                    await session.commit()

            async with async_session_factory() as session:
                stmt = select(RagEmbedding).where(RagEmbedding.organization_id == test_org.id)
                rows = (await session.execute(stmt)).scalars().all()
                assert len(rows) == 5

    async def test_tenant_scoped_isolation(self):
        """Verify that organization A cannot overwrite or delete organization B's chunks."""
        async with create_test_org() as test_org:
            provider = MockEmbeddingProvider(dimension=384)
            slug = f"other-org-{uuid.uuid4().hex[:12]}"
            async with async_session_factory() as session:
                other_org = Organization(name=f"Other Org {uuid.uuid4().hex[:8]}", slug=slug)
                session.add(other_org)
                await session.commit()
                await session.refresh(other_org)
                other_org_id = other_org.id

            try:
                # Sync chunk with same chunk_id into both orgs
                item = SyncItem(chunk_id="shared-id-name", source_type="EVIDENCE", text="Text for org A")
                async with async_session_factory() as session:
                    await sync_embeddings(
                        session=session,
                        organization_id=test_org.id,
                        items=[item],
                        provider=provider,
                        allow_mock=True,
                    )
                    await session.commit()

                item_b = SyncItem(chunk_id="shared-id-name", source_type="EVIDENCE", text="Text for org B")
                async with async_session_factory() as session:
                    await sync_embeddings(
                        session=session,
                        organization_id=other_org_id,
                        items=[item_b],
                        provider=provider,
                        allow_mock=True,
                    )
                    await session.commit()

                # Confirm both distinct rows exist isolated by tenant
                async with async_session_factory() as session:
                    row_a = (
                        await session.execute(
                            select(RagEmbedding).where(
                                RagEmbedding.organization_id == test_org.id,
                                RagEmbedding.chunk_id == "shared-id-name",
                            )
                        )
                    ).scalar_one()
                    row_b = (
                        await session.execute(
                            select(RagEmbedding).where(
                                RagEmbedding.organization_id == other_org_id,
                                RagEmbedding.chunk_id == "shared-id-name",
                            )
                        )
                    ).scalar_one()

                    assert row_a.organization_id == test_org.id
                    assert row_b.organization_id == other_org_id
                    assert row_a.chunk_text == "Text for org A"
                    assert row_b.chunk_text == "Text for org B"
            finally:
                async with async_session_factory() as session:
                    del_org = await session.get(Organization, other_org_id)
                    if del_org:
                        await session.delete(del_org)
                        await session.commit()

    async def test_stale_chunk_reconciliation(self):
        async with create_test_org() as test_org:
            provider = MockEmbeddingProvider(dimension=384)
            items = [
                SyncItem(chunk_id="active-1", source_type="EVIDENCE", text="Active evidence 1"),
                SyncItem(chunk_id="active-2", source_type="EVIDENCE", text="Active evidence 2"),
                SyncItem(chunk_id="stale-3", source_type="EVIDENCE", text="Stale evidence 3"),
            ]

            async with async_session_factory() as session:
                await sync_embeddings(
                    session=session,
                    organization_id=test_org.id,
                    items=items,
                    provider=provider,
                    allow_mock=True,
                )
                await session.commit()

            # Reconcile: only active-1 and active-2 are active now
            async with async_session_factory() as session:
                deleted = await reconcile_stale_chunks(
                    session=session,
                    organization_id=test_org.id,
                    active_chunk_ids={"active-1", "active-2"},
                )
                await session.commit()

            assert deleted == 1

            async with async_session_factory() as session:
                stmt = select(RagEmbedding.chunk_id).where(RagEmbedding.organization_id == test_org.id)
                remaining_ids = set((await session.execute(stmt)).scalars().all())
                assert remaining_ids == {"active-1", "active-2"}

    async def test_cascade_delete_on_organization_removal(self):
        """Verifies foreign key ON DELETE CASCADE clears embeddings when organization is deleted."""
        slug = f"cascade-org-{uuid.uuid4().hex[:12]}"
        async with async_session_factory() as session:
            org = Organization(name=f"Cascade Org {uuid.uuid4().hex[:8]}", slug=slug)
            session.add(org)
            await session.commit()
            await session.refresh(org)
            org_id = org.id

        provider = MockEmbeddingProvider(dimension=384)
        item = SyncItem(chunk_id="cascade-chunk", source_type="EVIDENCE", text="Cascade text")

        async with async_session_factory() as session:
            await sync_embeddings(
                session=session,
                organization_id=org_id,
                items=[item],
                provider=provider,
                allow_mock=True,
            )
            await session.commit()

        # Delete organization
        async with async_session_factory() as session:
            db_org = await session.get(Organization, org_id)
            await session.delete(db_org)
            await session.commit()

        # Verify embeddings were cascaded
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    select(RagEmbedding).where(RagEmbedding.organization_id == org_id)
                )
            ).scalars().all()
            assert len(rows) == 0

    async def test_sync_rejects_job_from_another_organization(self):
        """Rejects embedding item if job_id belongs to a different organization."""
        provider = MockEmbeddingProvider(dimension=384)
        async with create_test_org() as org_a:
            async with create_test_org() as org_b:
                # Create job under Org B
                async with async_session_factory() as session:
                    _, job_b = await _create_test_user_and_job(session, org_b.id)
                    await session.commit()
                    job_b_id = job_b.id

                # Attempt to sync into Org A referencing job_b
                item = SyncItem(
                    chunk_id="foreign-job-chunk",
                    source_type="JOB_DESCRIPTION",
                    text="Text referencing job B",
                    job_id=job_b_id,
                )
                async with async_session_factory() as session:
                    with pytest.raises(EmbeddingSyncError, match="Scope violation.*Job"):
                        await sync_embeddings(
                            session=session,
                            organization_id=org_a.id,
                            items=[item],
                            provider=provider,
                            allow_mock=True,
                        )

    async def test_sync_rejects_application_from_another_organization(self):
        """Rejects embedding item if application_id belongs to a different organization."""
        provider = MockEmbeddingProvider(dimension=384)
        async with create_test_org() as org_a:
            async with create_test_org() as org_b:
                async with async_session_factory() as session:
                    _, job_b = await _create_test_user_and_job(session, org_b.id)
                    cand = Candidate(full_name="Bob", email=f"bob-{uuid.uuid4().hex[:8]}@example.com")
                    session.add(cand)
                    await session.flush()
                    app_b = Application(candidate_id=cand.id, job_id=job_b.id)
                    session.add(app_b)
                    await session.commit()
                    app_b_id = app_b.id

                item = SyncItem(
                    chunk_id="foreign-app-chunk",
                    source_type="CANDIDATE_PROFILE",
                    text="Profile for App in Org B",
                    application_id=app_b_id,
                )
                async with async_session_factory() as session:
                    with pytest.raises(EmbeddingSyncError, match="Scope violation.*Application"):
                        await sync_embeddings(
                            session=session,
                            organization_id=org_a.id,
                            items=[item],
                            provider=provider,
                            allow_mock=True,
                        )

    async def test_sync_rejects_application_job_scope_mismatch(self):
        """Rejects embedding item when application belongs to Job 1 but item specifies Job 2."""
        provider = MockEmbeddingProvider(dimension=384)
        async with create_test_org() as org:
            async with async_session_factory() as session:
                user, job1 = await _create_test_user_and_job(session, org.id)
                job2 = Job(
                    organization_id=org.id,
                    title="Job 2",
                    description="Desc 2",
                    created_by=user.id,
                )
                cand = Candidate(full_name="Charlie", email=f"charlie-{uuid.uuid4().hex[:8]}@example.com")
                session.add_all([cand, job2])
                await session.flush()
                app = Application(candidate_id=cand.id, job_id=job1.id)
                session.add(app)
                await session.commit()
                app_id, job2_id = app.id, job2.id

            # Item claims application belongs to Job 2
            item = SyncItem(
                chunk_id="mismatched-scope-chunk",
                source_type="CANDIDATE_PROFILE",
                text="Mismatched scope text",
                application_id=app_id,
                job_id=job2_id,
            )
            async with async_session_factory() as session:
                with pytest.raises(EmbeddingSyncError, match="Scope conflict"):
                    await sync_embeddings(
                        session=session,
                        organization_id=org.id,
                        items=[item],
                        provider=provider,
                        allow_mock=True,
                    )

    async def test_reconciliation_rejects_other_tenant_scope(self):
        """Rejects reconciliation if job_id belongs to another organization."""
        async with create_test_org() as org_a:
            async with create_test_org() as org_b:
                async with async_session_factory() as session:
                    _, job_b = await _create_test_user_and_job(session, org_b.id)
                    await session.commit()
                    job_b_id = job_b.id

                async with async_session_factory() as session:
                    with pytest.raises(EmbeddingSyncError, match="Reconciliation scope violation"):
                        await reconcile_stale_chunks(
                            session=session,
                            organization_id=org_a.id,
                            active_chunk_ids={"dummy"},
                            job_id=job_b_id,
                        )

    async def test_reconciliation_empty_authoritative_set_cleans_scope(self):
        """When active_chunk_ids is empty for a scoped job, all chunks in that job are purged."""
        provider = MockEmbeddingProvider(dimension=384)
        async with create_test_org() as org:
            async with async_session_factory() as session:
                _, job = await _create_test_user_and_job(session, org.id)
                await session.commit()
                job_id = job.id

            item1 = SyncItem(chunk_id="job-c1", source_type="JOB_DESCRIPTION", text="Chunk 1", job_id=job_id)
            item2 = SyncItem(chunk_id="job-c2", source_type="JOB_DESCRIPTION", text="Chunk 2", job_id=job_id)
            async with async_session_factory() as session:
                await sync_embeddings(
                    session=session,
                    organization_id=org.id,
                    items=[item1, item2],
                    provider=provider,
                    allow_mock=True,
                )
                await session.commit()

            # Reconcile with 0 active chunks for job_id
            async with async_session_factory() as session:
                deleted = await reconcile_stale_chunks(
                    session=session,
                    organization_id=org.id,
                    active_chunk_ids=set(),
                    job_id=job_id,
                )
                await session.commit()

            assert deleted == 2
            async with async_session_factory() as session:
                rows = (
                    await session.execute(
                        select(RagEmbedding).where(
                            RagEmbedding.organization_id == org.id,
                            RagEmbedding.job_id == job_id,
                        )
                    )
                ).scalars().all()
                assert len(rows) == 0

    async def test_transaction_rollback_leaves_no_orphaned_rows(self):
        """Verifies that an error during sync leaves no partially written records upon transaction rollback."""
        provider = MockEmbeddingProvider(dimension=384)
        async with create_test_org() as org:
            valid_item = SyncItem(chunk_id="tx-chunk-1", source_type="EVIDENCE", text="Valid text")
            invalid_item = SyncItem(
                chunk_id="tx-chunk-2",
                source_type="EVIDENCE",
                text="Invalid scope",
                job_id=uuid.uuid4(),  # Non-existent job
            )

            try:
                async with async_session_factory() as session:
                    async with session.begin():
                        await sync_embeddings(
                            session=session,
                            organization_id=org.id,
                            items=[valid_item, invalid_item],
                            provider=provider,
                            allow_mock=True,
                        )
            except EmbeddingSyncError:
                pass  # Expected error

            # Confirm no rows exist for this org
            async with async_session_factory() as session:
                rows = (
                    await session.execute(
                        select(RagEmbedding).where(RagEmbedding.organization_id == org.id)
                    )
                ).scalars().all()
                assert len(rows) == 0

