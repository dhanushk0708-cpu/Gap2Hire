import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.roles import UserRole
from app.core.security import create_access_token, hash_password
from app.db.session import async_session_factory
from app.main import app
from app.models.user import User
from app.schemas.capability import CapabilityImportance
from app.schemas.jd_analysis import SuggestedCapability
from tests.test_jobs import create_registered_client


@pytest.mark.asyncio
async def test_hr_review_full_workflow():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        # 1. Create a Job
        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "title": "Fullstack Lead",
                "description": "Lead web app development with Python, React, and PostgreSQL.",
            },
        )
        assert job_resp.status_code == 201
        job_id = job_resp.json()["id"]

        # 2. Extract AI suggestions (Feature 3 mock)
        ai_suggestions = [
            SuggestedCapability(
                name="Python",
                description="Backend programming language",
                importance=CapabilityImportance.HIGH,
            ),
            SuggestedCapability(
                name="React",
                description="Frontend UI framework",
                importance=CapabilityImportance.HIGH,
            ),
            SuggestedCapability(
                name="PostgreSQL",
                description="Database system",
                importance=CapabilityImportance.MEDIUM,
            ),
        ]

        with patch(
            "app.api.jd_analysis.extract_capabilities_from_jd",
            new_callable=AsyncMock,
            return_value=ai_suggestions,
        ):
            analyze_resp = await client.post(
                f"/api/v1/jobs/{job_id}/analyze",
                headers=headers,
            )
            assert analyze_resp.status_code == 200
            suggestions = analyze_resp.json()["suggested_capabilities"]
            assert len(suggestions) == 3

        # Confirm DB capabilities are still 0 before HR approval
        caps_before = (
            await client.get(
                f"/api/v1/jobs/{job_id}/capabilities",
                headers=headers,
            )
        ).json()
        assert len(caps_before) == 0

        # 3. HR bulk accepts selected suggestions into final capability set
        batch_payload = {
            "capabilities": [
                {
                    "name": suggestions[0]["name"],
                    "description": suggestions[0]["description"],
                    "importance": suggestions[0]["importance"],
                },
                {
                    "name": suggestions[1]["name"],
                    "description": suggestions[1]["description"],
                    "importance": suggestions[1]["importance"],
                },
            ]
        }
        batch_resp = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities/batch",
            headers=headers,
            json=batch_payload,
        )
        assert batch_resp.status_code == 201
        saved_caps = batch_resp.json()
        assert len(saved_caps) == 2
        cap_python_id = saved_caps[0]["id"]
        cap_react_id = saved_caps[1]["id"]

        # 4. HR manually adds a custom capability
        manual_resp = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={
                "name": "System Architecture",
                "description": "Distributed system design",
                "importance": "CRITICAL",
            },
        )
        assert manual_resp.status_code == 201
        cap_arch_id = manual_resp.json()["id"]

        # 5. HR edits a capability (change name and importance)
        patch_resp = await client.patch(
            f"/api/v1/capabilities/{cap_python_id}",
            headers=headers,
            json={
                "name": "Advanced Python 3.11+",
                "importance": "CRITICAL",
            },
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "Advanced Python 3.11+"
        assert patch_resp.json()["importance"] == "CRITICAL"

        # 6. HR deletes a capability (remove React capability)
        del_resp = await client.delete(
            f"/api/v1/capabilities/{cap_react_id}",
            headers=headers,
        )
        assert del_resp.status_code == 204

        # 7. HR views final capability set
        final_caps = (
            await client.get(
                f"/api/v1/jobs/{job_id}/capabilities",
                headers=headers,
            )
        ).json()
        assert len(final_caps) == 2
        names = [c["name"] for c in final_caps]
        assert "Advanced Python 3.11+" in names
        assert "System Architecture" in names
        assert "React" not in names


@pytest.mark.asyncio
async def test_hr_review_unauthenticated_rejected():
    fake_job_id = str(uuid.uuid4())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            f"/api/v1/jobs/{fake_job_id}/capabilities/batch",
            json={"capabilities": [{"name": "Skill", "importance": "HIGH"}]},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_hr_review_candidate_forbidden():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        org_id = uuid.UUID(auth["organization_id"])

        candidate_user = User(
            organization_id=org_id,
            email=f"candidate-{uuid.uuid4()}@gap2hire.com",
            password_hash=hash_password("Pass123!"),
            full_name="Candidate Person",
            role=UserRole.CANDIDATE.value,
        )
        async with async_session_factory() as session:
            session.add(candidate_user)
            await session.commit()
            await session.refresh(candidate_user)

        candidate_headers = {
            "Authorization": f"Bearer {create_access_token(str(candidate_user.id))}"
        }
        fake_job_id = str(uuid.uuid4())

        resp = await client.post(
            f"/api/v1/jobs/{fake_job_id}/capabilities/batch",
            headers=candidate_headers,
            json={"capabilities": [{"name": "Skill", "importance": "HIGH"}]},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_hr_review_cross_tenant_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_a = await create_registered_client(client)
        auth_b = await create_registered_client(client)

        # Org A creates a Job
        job_a_resp = await client.post(
            "/api/v1/jobs",
            headers=auth_a["headers"],
            json={"title": "Org A Job", "description": "Desc"},
        )
        job_a_id = job_a_resp.json()["id"]

        # Org B attempts bulk batch capability creation on Org A's job -> 404
        resp_b = await client.post(
            f"/api/v1/jobs/{job_a_id}/capabilities/batch",
            headers=auth_b["headers"],
            json={"capabilities": [{"name": "Skill B", "importance": "HIGH"}]},
        )
        assert resp_b.status_code == 404


@pytest.mark.asyncio
async def test_hr_review_validation_failure():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "Test Job", "description": "Desc"},
        )
        job_id = job_resp.json()["id"]

        # Empty capabilities list in batch
        resp1 = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities/batch",
            headers=headers,
            json={"capabilities": []},
        )
        assert resp1.status_code == 422

        # Invalid item inside batch list (empty name)
        resp2 = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities/batch",
            headers=headers,
            json={"capabilities": [{"name": "", "importance": "HIGH"}]},
        )
        assert resp2.status_code == 422
