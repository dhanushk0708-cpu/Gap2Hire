from datetime import datetime
from uuid import UUID, uuid4
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.main import app
from app.models.candidate_source import CandidateSource
from app.services.candidate_sources import mark_source_inspected


async def setup_test_tenant_and_application(client: AsyncClient):
    """Helper to create an organization, job, candidate, and application."""
    org_name = f"Sources Corp {uuid4()}"
    email = f"manager-{uuid4()}@gap2hire.com"
    password = "SecurePassword123!"

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Source Test Manager",
            "organization_name": org_name,
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Job
    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Full Stack AI Engineer",
            "description": "Python, FastAPI, LangGraph, React",
        },
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # Create Candidate
    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={
            "email": f"candidate-{uuid4()}@example.com",
            "full_name": "Jane Candidate",
        },
    )
    assert cand_resp.status_code == 201
    candidate_id = cand_resp.json()["id"]

    # Create Application
    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={
            "candidate_id": candidate_id,
            "job_id": job_id,
        },
    )
    assert app_resp.status_code == 201
    application_id = app_resp.json()["id"]

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    org_id = me_resp.json()["organization_id"]

    return {
        "headers": headers,
        "organization_id": org_id,
        "job_id": job_id,
        "candidate_id": candidate_id,
        "application_id": application_id,
    }


# 1. Create candidate source successfully
@pytest.mark.asyncio
async def test_create_candidate_source_success():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://github.com/janedoe/gap2hire-demo",
                "source_type": "GITHUB",
                "discovered_from": "resume.pdf",
                "discovery_depth": 0,
                "status": "DISCOVERED",
                "relevance": "HIGH",
                "title": "GitHub Profile / Repositories",
                "metadata": {"stars": 42, "language": "Python"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://github.com/janedoe/gap2hire-demo"
        assert data["source_type"] == "GITHUB"
        assert data["discovered_from"] == "resume.pdf"
        assert data["discovery_depth"] == 0
        assert data["status"] == "DISCOVERED"
        assert data["relevance"] == "HIGH"
        assert data["title"] == "GitHub Profile / Repositories"
        assert data["metadata"] == {"stars": 42, "language": "Python"}
        assert data["application_id"] == app_id
        assert "id" in data


# 2. List sources for an application
@pytest.mark.asyncio
async def test_list_candidate_sources_for_application():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        # Create two sources
        await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://github.com/janedoe",
                "source_type": "GITHUB",
                "discovery_depth": 0,
            },
        )
        await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://janedoe.dev/portfolio",
                "source_type": "PORTFOLIO",
                "discovery_depth": 1,
                "discovered_from": "https://github.com/janedoe",
            },
        )

        list_resp = await client.get(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
        )
        assert list_resp.status_code == 200
        sources = list_resp.json()
        assert len(sources) >= 2
        urls = [s["url"] for s in sources]
        assert "https://github.com/janedoe" in urls
        assert "https://janedoe.dev/portfolio" in urls


# 3. Get a source by ID
@pytest.mark.asyncio
async def test_get_candidate_source_by_id():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        create_resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://linkedin.com/in/janedoe",
                "source_type": "LINKEDIN",
                "status": "QUEUED",
            },
        )
        source_id = create_resp.json()["id"]

        get_resp = await client.get(
            f"/api/v1/candidate-sources/{source_id}",
            headers=headers,
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == source_id
        assert data["url"] == "https://linkedin.com/in/janedoe"
        assert data["source_type"] == "LINKEDIN"
        assert data["status"] == "QUEUED"


# 4. Update source fields
@pytest.mark.asyncio
async def test_update_candidate_source():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        create_resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://janedoe.dev/blog/fastapi",
                "source_type": "BLOG",
                "status": "DISCOVERED",
            },
        )
        source_id = create_resp.json()["id"]

        update_resp = await client.patch(
            f"/api/v1/candidate-sources/{source_id}",
            headers=headers,
            json={
                "status": "SKIPPED",
                "relevance": "LOW",
                "title": "Blog post on FastAPI",
                "metadata": {"reason": "Not related to required stack"},
            },
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["status"] == "SKIPPED"
        assert updated["relevance"] == "LOW"
        assert updated["title"] == "Blog post on FastAPI"
        assert updated["metadata"] == {"reason": "Not related to required stack"}


# 5. Mark source as inspected
@pytest.mark.asyncio
async def test_mark_candidate_source_inspected_service():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]
        org_id = UUID(setup["organization_id"])

        create_resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://github.com/janedoe/evidence-repo",
                "source_type": "GITHUB",
                "status": "QUEUED",
            },
        )
        source_id = UUID(create_resp.json()["id"])

        async with async_session_factory() as session:
            inspected = await mark_source_inspected(
                session=session,
                organization_id=org_id,
                source_id=source_id,
                relevance="HIGH",
                title="Inspected Project Repo",
                metadata={"commits": 150, "verified": True},
            )
            assert inspected.status == "INSPECTED"
            assert inspected.relevance == "HIGH"
            assert inspected.title == "Inspected Project Repo"
            assert inspected.last_inspected_at is not None
            assert inspected.metadata_ == {"commits": 150, "verified": True}


# 6. Invalid status is rejected
@pytest.mark.asyncio
async def test_invalid_status_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://github.com/janedoe",
                "source_type": "GITHUB",
                "status": "INVALID_STATUS_VALUE",
            },
        )
        assert resp.status_code == 422


# 7. Negative discovery_depth is rejected
@pytest.mark.asyncio
async def test_negative_discovery_depth_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://github.com/janedoe",
                "source_type": "GITHUB",
                "discovery_depth": -1,
            },
        )
        assert resp.status_code == 422


# 8. Empty URL is rejected
@pytest.mark.asyncio
async def test_empty_url_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "   ",
                "source_type": "GITHUB",
            },
        )
        assert resp.status_code == 422


# 9. Missing application is handled correctly
@pytest.mark.asyncio
async def test_missing_application_returns_404():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        missing_app_id = uuid4()

        resp = await client.post(
            f"/api/v1/applications/{missing_app_id}/sources",
            headers=headers,
            json={
                "url": "https://github.com/janedoe",
                "source_type": "GITHUB",
            },
        )
        assert resp.status_code == 404


# 10. Cross-organization access is denied (Tenant isolation)
@pytest.mark.asyncio
async def test_cross_organization_access_denied():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup_a = await setup_test_tenant_and_application(client)
        setup_b = await setup_test_tenant_and_application(client)

        headers_a = setup_a["headers"]
        headers_b = setup_b["headers"]
        app_a_id = setup_a["application_id"]

        # Org A creates a source
        create_resp = await client.post(
            f"/api/v1/applications/{app_a_id}/sources",
            headers=headers_a,
            json={
                "url": "https://github.com/tenant-a/project",
                "source_type": "GITHUB",
            },
        )
        assert create_resp.status_code == 201
        source_id = create_resp.json()["id"]

        # Org B tries to list sources for Org A's application -> 404
        list_resp_b = await client.get(
            f"/api/v1/applications/{app_a_id}/sources",
            headers=headers_b,
        )
        assert list_resp_b.status_code == 404

        # Org B tries to get Org A's candidate source -> 404
        get_resp_b = await client.get(
            f"/api/v1/candidate-sources/{source_id}",
            headers=headers_b,
        )
        assert get_resp_b.status_code == 404

        # Org B tries to update Org A's candidate source -> 404
        patch_resp_b = await client.patch(
            f"/api/v1/candidate-sources/{source_id}",
            headers=headers_b,
            json={"status": "INSPECTED"},
        )
        assert patch_resp_b.status_code == 404


# 11. Cascade deletion works on application delete
@pytest.mark.asyncio
async def test_cascade_deletion_on_application_delete():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        setup = await setup_test_tenant_and_application(client)
        headers = setup["headers"]
        app_id = setup["application_id"]

        create_resp = await client.post(
            f"/api/v1/applications/{app_id}/sources",
            headers=headers,
            json={
                "url": "https://github.com/janedoe/to-be-deleted",
                "source_type": "GITHUB",
            },
        )
        assert create_resp.status_code == 201
        source_id = UUID(create_resp.json()["id"])

        # Directly delete application from DB
        async with async_session_factory() as session:
            from app.models.application import Application
            application = await session.get(Application, UUID(app_id))
            assert application is not None
            await session.delete(application)
            await session.commit()

        # Check candidate source was deleted via CASCADE
        async with async_session_factory() as session:
            stmt = select(CandidateSource).where(CandidateSource.id == source_id)
            source_in_db = await session.scalar(stmt)
            assert source_in_db is None
