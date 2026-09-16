import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import async_session_factory
from app.main import app
from app.models.evidence import Evidence
from tests.test_candidates_applications import (
    create_candidate_user,
    create_registered_client,
)


async def setup_summary_application(
    client: AsyncClient,
    auth: dict,
    capabilities: list[dict],
) -> tuple[str, list[dict]]:
    headers = auth["headers"]

    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "Backend Engineer", "description": "Python, FastAPI, Redis"},
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    created_caps = []
    for cap in capabilities:
        cap_resp = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json=cap,
        )
        assert cap_resp.status_code == 201
        created_caps.append(cap_resp.json())

    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={"full_name": "Summary Candidate", "email": f"cand.{uuid.uuid4()}@example.com"},
    )
    assert cand_resp.status_code == 201
    candidate_id = cand_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={"candidate_id": candidate_id, "job_id": job_id},
    )
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    return app_id, created_caps


async def inject_evidence(
    application_id: str,
    capability_id: str,
    strength: str,
    content: str | None,
):
    async with async_session_factory() as session:
        ev = Evidence(
            application_id=uuid.UUID(application_id),
            capability_id=uuid.UUID(capability_id),
            source_type="RESUME",
            strength=strength,
            content=content,
        )
        session.add(ev)
        await session.commit()


@pytest.mark.asyncio
async def test_successful_summary_with_known_and_unknown_capabilities():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[
                {"name": "Python", "description": "Language", "importance": "HIGH"},
                {"name": "FastAPI", "description": "Framework", "importance": "HIGH"},
                {"name": "PostgreSQL", "description": "Database", "importance": "MEDIUM"},
                {"name": "Redis", "description": "Cache", "importance": "MEDIUM"},
            ],
        )

        await inject_evidence(app_id, caps[0]["id"], "STRONG", "Built Python microservices")
        await inject_evidence(app_id, caps[1]["id"], "MODERATE", "Used FastAPI endpoints")
        await inject_evidence(app_id, caps[2]["id"], "WEAK", "Basic SQL queries")

        response = await client.get(
            f"/api/v1/applications/{app_id}/evidence/summary",
            headers=auth["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == app_id
        summary_caps = data["capabilities"]

        assert len(summary_caps) == 4

        c0 = next(c for c in summary_caps if c["capability_id"] == caps[0]["id"])
        assert c0["name"] == "Python"
        assert c0["state"] == "KNOWN"
        assert c0["strength"] == "STRONG"
        assert c0["evidence"] == "Built Python microservices"

        c1 = next(c for c in summary_caps if c["capability_id"] == caps[1]["id"])
        assert c1["name"] == "FastAPI"
        assert c1["state"] == "KNOWN"
        assert c1["strength"] == "MODERATE"
        assert c1["evidence"] == "Used FastAPI endpoints"

        c2 = next(c for c in summary_caps if c["capability_id"] == caps[2]["id"])
        assert c2["name"] == "PostgreSQL"
        assert c2["state"] == "KNOWN"
        assert c2["strength"] == "WEAK"
        assert c2["evidence"] == "Basic SQL queries"

        c3 = next(c for c in summary_caps if c["capability_id"] == caps[3]["id"])
        assert c3["name"] == "Redis"
        assert c3["state"] == "UNKNOWN"
        assert c3["strength"] == "INSUFFICIENT"
        assert c3["evidence"] is None


@pytest.mark.asyncio
async def test_all_capabilities_missing_evidence():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[
                {"name": "Docker", "description": "Containers"},
                {"name": "Kubernetes", "description": "Orchestration"},
            ],
        )

        response = await client.get(
            f"/api/v1/applications/{app_id}/evidence/summary",
            headers=auth["headers"],
        )
        assert response.status_code == 200
        summary_caps = response.json()["capabilities"]
        assert len(summary_caps) == 2

        for c in summary_caps:
            assert c["state"] == "UNKNOWN"
            assert c["strength"] == "INSUFFICIENT"
            assert c["evidence"] is None


@pytest.mark.asyncio
async def test_all_job_capabilities_appear_exactly_once():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[
                {"name": "Cap 1", "description": "Desc 1"},
                {"name": "Cap 2", "description": "Desc 2"},
                {"name": "Cap 3", "description": "Desc 3"},
            ],
        )

        response = await client.get(
            f"/api/v1/applications/{app_id}/evidence/summary",
            headers=auth["headers"],
        )
        assert response.status_code == 200
        summary_caps = response.json()["capabilities"]

        returned_cap_ids = [c["capability_id"] for c in summary_caps]
        expected_cap_ids = [c["id"] for c in caps]

        assert len(returned_cap_ids) == len(expected_cap_ids)
        assert set(returned_cap_ids) == set(expected_cap_ids)


@pytest.mark.asyncio
async def test_evidence_summary_is_read_only():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "Go", "description": "Language"}],
        )

        res1 = await client.get(
            f"/api/v1/applications/{app_id}/evidence/summary",
            headers=auth["headers"],
        )
        assert res1.status_code == 200

        async with async_session_factory() as session:
            ev_list = (
                await session.scalars(
                    __import__("sqlalchemy", fromlist=["select"]).select(Evidence).where(Evidence.application_id == uuid.UUID(app_id))
                )
            ).all()
            assert len(ev_list) == 0


@pytest.mark.asyncio
async def test_missing_capability_not_labeled_as_no_skill_or_failed():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "GraphQL", "description": "API query"}],
        )

        response = await client.get(
            f"/api/v1/applications/{app_id}/evidence/summary",
            headers=auth["headers"],
        )
        assert response.status_code == 200
        c_summary = response.json()["capabilities"][0]

        assert c_summary["state"] == "UNKNOWN"
        assert c_summary["strength"] == "INSUFFICIENT"
        assert c_summary["evidence"] is None
        assert "no skill" not in str(c_summary).lower()
        assert "failed" not in str(c_summary).lower()
        assert "rejected" not in str(c_summary).lower()


@pytest.mark.asyncio
async def test_unauthenticated_evidence_summary():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get(
            f"/api/v1/applications/{uuid.uuid4()}/evidence/summary"
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_candidate_role_evidence_summary_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        cand_auth = await create_candidate_user(auth["organization_id"])

        res = await client.get(
            f"/api/v1/applications/{uuid.uuid4()}/evidence/summary",
            headers=cand_auth["headers"],
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_evidence_summary_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_company_1 = await create_registered_client(client)
        auth_company_2 = await create_registered_client(client)

        app_id, _ = await setup_summary_application(
            client,
            auth_company_1,
            capabilities=[{"name": "Python", "description": "Lang"}],
        )

        res = await client.get(
            f"/api/v1/applications/{app_id}/evidence/summary",
            headers=auth_company_2["headers"],
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_non_existent_application_evidence_summary():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        res = await client.get(
            f"/api/v1/applications/{uuid.uuid4()}/evidence/summary",
            headers=auth["headers"],
        )
        assert res.status_code == 404
