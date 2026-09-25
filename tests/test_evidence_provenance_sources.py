from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.main import app
from app.models.candidate_source import CandidateSource
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceProvenance, EvidenceResponse, EvidenceStrength
from app.services.evidence import (
    CandidateSourceNotFoundError,
    InvalidCandidateSourceError,
    get_application_evidence_summary,
    record_candidate_evidence,
)


async def setup_test_context(client: AsyncClient):
    """Creates an organization, manager token, job, capability, candidate, and application."""
    org_name = f"Evidence Corp {uuid4()}"
    email = f"manager-{uuid4()}@evidencecorp.com"
    password = "SecurePassword123!"

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Evidence Test Manager",
            "organization_name": org_name,
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    org_id = me_resp.json()["organization_id"]

    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "FastAPI AI Engineer", "description": "Backend services and LLMs"},
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    cap_resp = await client.post(
        f"/api/v1/jobs/{job_id}/capabilities",
        headers=headers,
        json={"name": "FastAPI", "description": "High performance async web framework"},
    )
    assert cap_resp.status_code == 201
    cap_id = cap_resp.json()["id"]

    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={"email": f"cand-{uuid4()}@gmail.com", "full_name": "Test Candidate"},
    )
    assert cand_resp.status_code == 201
    cand_id = cand_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={"candidate_id": cand_id, "job_id": job_id},
    )
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    return {
        "headers": headers,
        "org_id": org_id,
        "job_id": job_id,
        "cap_id": cap_id,
        "cand_id": cand_id,
        "app_id": app_id,
    }


@pytest.mark.asyncio
async def test_evidence_created_without_source_id():
    """1. Test that evidence can be created without source_id (e.g. general resume claim)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        async with async_session_factory() as session:
            ev = await record_candidate_evidence(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
                capability_id=ctx["cap_id"],
                source_type="RESUME",
                strength=EvidenceStrength.STRONG,
                provenance=EvidenceProvenance.CLAIM,
                content="5 years of FastAPI experience stated on resume",
                candidate_source_id=None,
            )

            assert ev.id is not None
            assert ev.candidate_source_id is None
            assert ev.provenance == "CLAIM"
            assert ev.strength == "STRONG"


@pytest.mark.asyncio
async def test_evidence_referencing_valid_candidate_source():
    """2. Test that evidence can reference a valid CandidateSource with DEMONSTRATED provenance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        # Create a candidate source
        src_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/sources",
            headers=ctx["headers"],
            json={
                "url": "https://github.com/candidate/fastapi-microservices",
                "source_type": "GITHUB",
                "status": "INSPECTED",
            },
        )
        assert src_resp.status_code == 201
        source_id = src_resp.json()["id"]

        async with async_session_factory() as session:
            ev = await record_candidate_evidence(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
                capability_id=ctx["cap_id"],
                source_type="GITHUB",
                strength=EvidenceStrength.STRONG,
                provenance=EvidenceProvenance.DEMONSTRATED,
                content="Maintained async FastAPI repository with automated test suite",
                candidate_source_id=source_id,
            )

            assert str(ev.candidate_source_id) == source_id
            assert ev.provenance == "DEMONSTRATED"
            assert ev.source_type == "GITHUB"


@pytest.mark.asyncio
async def test_evidence_response_schema_exposes_source_id():
    """3. Test that EvidenceResponse serialization exposes both source_id and candidate_source_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        src_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/sources",
            headers=ctx["headers"],
            json={
                "url": "https://docs.candidate.dev",
                "source_type": "DOCS",
                "status": "DISCOVERED",
            },
        )
        source_id = src_resp.json()["id"]

        async with async_session_factory() as session:
            ev = await record_candidate_evidence(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
                capability_id=ctx["cap_id"],
                source_type="DOCS",
                strength=EvidenceStrength.MODERATE,
                provenance=EvidenceProvenance.CORROBORATED,
                content="Architecture documentation shows FastAPI schema design",
                candidate_source_id=source_id,
            )

            schema = EvidenceResponse.model_validate(ev)
            assert str(schema.source_id) == source_id
            assert str(schema.candidate_source_id) == source_id
            assert schema.provenance == EvidenceProvenance.CORROBORATED


@pytest.mark.asyncio
async def test_evidence_candidate_source_relationship():
    """4. Test that Evidence can load its related CandidateSource model directly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        src_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/sources",
            headers=ctx["headers"],
            json={
                "url": "https://gitlab.com/candidate/pipeline",
                "source_type": "GITLAB",
                "status": "INSPECTED",
            },
        )
        source_id = src_resp.json()["id"]

        async with async_session_factory() as session:
            await record_candidate_evidence(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
                capability_id=ctx["cap_id"],
                source_type="GITLAB",
                strength=EvidenceStrength.STRONG,
                provenance=EvidenceProvenance.DEMONSTRATED,
                content="GitLab CI/CD pipeline building FastAPI containers",
                candidate_source_id=source_id,
            )

            # Query evidence with related candidate_source
            stmt = select(Evidence).where(
                Evidence.application_id == ctx["app_id"],
                Evidence.source_type == "GITLAB",
            )
            ev = await session.scalar(stmt)
            await session.refresh(ev, ["candidate_source"])

            assert ev.candidate_source is not None
            assert ev.candidate_source.url == "https://gitlab.com/candidate/pipeline"


@pytest.mark.asyncio
async def test_reject_candidate_source_from_different_application():
    """5. Test that linking a CandidateSource belonging to a different application is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx1 = await setup_test_context(client)

        # Create another candidate & application in same organization
        cand2_resp = await client.post(
            "/api/v1/candidates",
            headers=ctx1["headers"],
            json={"email": f"cand2-{uuid4()}@example.com", "full_name": "Second Candidate"},
        )
        cand2_id = cand2_resp.json()["id"]

        app2_resp = await client.post(
            "/api/v1/applications",
            headers=ctx1["headers"],
            json={"candidate_id": cand2_id, "job_id": ctx1["job_id"]},
        )
        app2_id = app2_resp.json()["id"]

        # Create source on application 2
        src2_resp = await client.post(
            f"/api/v1/applications/{app2_id}/sources",
            headers=ctx1["headers"],
            json={
                "url": "https://github.com/cand2/repo",
                "source_type": "GITHUB",
                "status": "DISCOVERED",
            },
        )
        source2_id = src2_resp.json()["id"]

        # Attempt to link source2 to application 1 evidence -> should fail
        async with async_session_factory() as session:
            with pytest.raises(InvalidCandidateSourceError):
                await record_candidate_evidence(
                    session=session,
                    organization_id=ctx1["org_id"],
                    application_id=ctx1["app_id"],
                    capability_id=ctx1["cap_id"],
                    source_type="GITHUB",
                    strength=EvidenceStrength.STRONG,
                    provenance=EvidenceProvenance.DEMONSTRATED,
                    content="Mismatched source",
                    candidate_source_id=source2_id,
                )


@pytest.mark.asyncio
async def test_reject_candidate_source_from_different_organization():
    """6. Test that linking a CandidateSource from another tenant organization is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx_tenant_a = await setup_test_context(client)
        ctx_tenant_b = await setup_test_context(client)

        # Create source in Tenant B
        src_b_resp = await client.post(
            f"/api/v1/applications/{ctx_tenant_b['app_id']}/sources",
            headers=ctx_tenant_b["headers"],
            json={
                "url": "https://github.com/tenant-b/repo",
                "source_type": "GITHUB",
                "status": "DISCOVERED",
            },
        )
        source_b_id = src_b_resp.json()["id"]

        # Attempt to link Tenant B's source in Tenant A's application -> should fail
        async with async_session_factory() as session:
            with pytest.raises(InvalidCandidateSourceError):
                await record_candidate_evidence(
                    session=session,
                    organization_id=ctx_tenant_a["org_id"],
                    application_id=ctx_tenant_a["app_id"],
                    capability_id=ctx_tenant_a["cap_id"],
                    source_type="GITHUB",
                    strength=EvidenceStrength.STRONG,
                    provenance=EvidenceProvenance.DEMONSTRATED,
                    content="Cross-tenant attack",
                    candidate_source_id=source_b_id,
                )


@pytest.mark.asyncio
async def test_deleting_candidate_source_sets_null_and_preserves_evidence():
    """7. Test ON DELETE SET NULL: deleting a CandidateSource does not delete the Evidence record."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        src_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/sources",
            headers=ctx["headers"],
            json={
                "url": "https://github.com/temp-user/temp-repo",
                "source_type": "GITHUB",
                "status": "INSPECTED",
            },
        )
        source_id = src_resp.json()["id"]

        async with async_session_factory() as session:
            ev = await record_candidate_evidence(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
                capability_id=ctx["cap_id"],
                source_type="GITHUB",
                strength=EvidenceStrength.STRONG,
                provenance=EvidenceProvenance.DEMONSTRATED,
                content="Historical evidence from repo",
                candidate_source_id=source_id,
            )
            evidence_id = ev.id

        # Delete the CandidateSource
        async with async_session_factory() as session:
            stmt = select(CandidateSource).where(CandidateSource.id == source_id)
            src_obj = await session.scalar(stmt)
            await session.delete(src_obj)
            await session.commit()

        # Check that Evidence record still exists with candidate_source_id = None
        async with async_session_factory() as session:
            stmt_ev = select(Evidence).where(Evidence.id == evidence_id)
            preserved_ev = await session.scalar(stmt_ev)

            assert preserved_ev is not None
            assert preserved_ev.candidate_source_id is None
            assert preserved_ev.provenance == "DEMONSTRATED"
            assert preserved_ev.content == "Historical evidence from repo"


@pytest.mark.asyncio
async def test_evidence_summary_surfaces_source_provenance():
    """8. Test that get_application_evidence_summary includes source_id and provenance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        src_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/sources",
            headers=ctx["headers"],
            json={
                "url": "https://github.com/candidate/portfolio-projects",
                "source_type": "GITHUB",
                "status": "INSPECTED",
            },
        )
        source_id = src_resp.json()["id"]

        async with async_session_factory() as session:
            await record_candidate_evidence(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
                capability_id=ctx["cap_id"],
                source_type="GITHUB",
                strength=EvidenceStrength.STRONG,
                provenance=EvidenceProvenance.DEMONSTRATED,
                content="Verified open-source implementation of FastAPI backend",
                candidate_source_id=source_id,
            )

            summary = await get_application_evidence_summary(
                session=session,
                application_id=ctx["app_id"],
                organization_id=ctx["org_id"],
            )

            assert len(summary.capabilities) == 1
            cap_summary = summary.capabilities[0]
            assert cap_summary.name == "FastAPI"
            assert cap_summary.strength == EvidenceStrength.STRONG
            assert cap_summary.provenance == EvidenceProvenance.DEMONSTRATED
            assert str(cap_summary.source_id) == source_id
            assert str(cap_summary.candidate_source_id) == source_id
            assert "Verified open-source" in cap_summary.evidence
