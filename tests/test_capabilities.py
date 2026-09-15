import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.roles import UserRole
from app.core.security import create_access_token, hash_password
from app.db.session import async_session_factory
from app.main import app
from app.models.user import User
from tests.test_jobs import create_registered_client


@pytest.mark.asyncio
async def test_capability_crud_authorized_flow():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        # Create Job
        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "title": "Backend Lead",
                "description": "Lead the backend engineering team.",
            },
        )
        assert job_resp.status_code == 201
        job_id = job_resp.json()["id"]

        # 1. Create Capability
        cap_resp = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={
                "name": "Python",
                "description": "Proficiency in Python 3.11+ async ecosystem",
                "importance": "HIGH",
            },
        )
        assert cap_resp.status_code == 201
        cap = cap_resp.json()
        cap_id = cap["id"]

        assert cap["job_id"] == job_id
        assert cap["name"] == "Python"
        assert cap["description"] == "Proficiency in Python 3.11+ async ecosystem"
        assert cap["importance"] == "HIGH"
        assert "created_at" in cap
        assert "updated_at" in cap

        # 2. List Capabilities for Job
        list_resp = await client.get(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
        )
        assert list_resp.status_code == 200
        cap_list = list_resp.json()
        assert len(cap_list) >= 1
        assert any(c["id"] == cap_id for c in cap_list)

        # 3. Update Capability
        patch_resp = await client.patch(
            f"/api/v1/capabilities/{cap_id}",
            headers=headers,
            json={
                "importance": "CRITICAL",
                "name": "Advanced Python & AsyncIO",
            },
        )
        assert patch_resp.status_code == 200
        updated_cap = patch_resp.json()
        assert updated_cap["name"] == "Advanced Python & AsyncIO"
        assert updated_cap["importance"] == "CRITICAL"

        # 4. Delete Capability
        del_resp = await client.delete(
            f"/api/v1/capabilities/{cap_id}",
            headers=headers,
        )
        assert del_resp.status_code == 204

        # Verify capability deleted from job
        list_after_del = await client.get(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
        )
        assert list_after_del.status_code == 200
        assert not any(c["id"] == cap_id for c in list_after_del.json())


@pytest.mark.asyncio
async def test_capability_belongs_to_correct_job():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        # Create Job 1
        job1_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "Job One", "description": "Desc 1"},
        )
        job1_id = job1_resp.json()["id"]

        # Create Job 2
        job2_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "Job Two", "description": "Desc 2"},
        )
        job2_id = job2_resp.json()["id"]

        # Add capability to Job 1
        cap_resp = await client.post(
            f"/api/v1/jobs/{job1_id}/capabilities",
            headers=headers,
            json={"name": "FastAPI", "importance": "HIGH"},
        )
        cap_id = cap_resp.json()["id"]

        # List capabilities for Job 1 -> contains capability
        caps_job1 = (await client.get(f"/api/v1/jobs/{job1_id}/capabilities", headers=headers)).json()
        assert any(c["id"] == cap_id for c in caps_job1)

        # List capabilities for Job 2 -> does NOT contain Job 1's capability
        caps_job2 = (await client.get(f"/api/v1/jobs/{job2_id}/capabilities", headers=headers)).json()
        assert not any(c["id"] == cap_id for c in caps_job2)


@pytest.mark.asyncio
async def test_capability_unauthenticated_access_rejected():
    fake_job_id = str(uuid.uuid4())
    fake_cap_id = str(uuid.uuid4())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        post_resp = await client.post(
            f"/api/v1/jobs/{fake_job_id}/capabilities",
            json={"name": "PostgreSQL"},
        )
        assert post_resp.status_code in (401, 403)

        get_resp = await client.get(f"/api/v1/jobs/{fake_job_id}/capabilities")
        assert get_resp.status_code in (401, 403)

        patch_resp = await client.patch(
            f"/api/v1/capabilities/{fake_cap_id}",
            json={"importance": "LOW"},
        )
        assert patch_resp.status_code in (401, 403)

        del_resp = await client.delete(f"/api/v1/capabilities/{fake_cap_id}")
        assert del_resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_candidate_cannot_manage_capabilities():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        org_id = uuid.UUID(auth["organization_id"])

        # Insert a candidate user
        candidate_user = User(
            organization_id=org_id,
            email=f"candidate-{uuid.uuid4()}@gap2hire.com",
            password_hash=hash_password("Pass123!"),
            full_name="Candidate",
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

        post_resp = await client.post(
            f"/api/v1/jobs/{fake_job_id}/capabilities",
            headers=candidate_headers,
            json={"name": "Docker"},
        )
        assert post_resp.status_code == 403

        get_resp = await client.get(
            f"/api/v1/jobs/{fake_job_id}/capabilities",
            headers=candidate_headers,
        )
        assert get_resp.status_code == 403


@pytest.mark.asyncio
async def test_cross_organization_capability_access_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_a = await create_registered_client(client)
        auth_b = await create_registered_client(client)

        # Org A creates a Job and a Capability
        job_a_resp = await client.post(
            "/api/v1/jobs",
            headers=auth_a["headers"],
            json={"title": "Org A Job", "description": "Desc"},
        )
        job_a_id = job_a_resp.json()["id"]

        cap_a_resp = await client.post(
            f"/api/v1/jobs/{job_a_id}/capabilities",
            headers=auth_a["headers"],
            json={"name": "Org A Skill", "importance": "HIGH"},
        )
        cap_a_id = cap_a_resp.json()["id"]

        # Org B attempts to create capability on Org A's Job -> 404
        post_b_resp = await client.post(
            f"/api/v1/jobs/{job_a_id}/capabilities",
            headers=auth_b["headers"],
            json={"name": "Malicious Skill"},
        )
        assert post_b_resp.status_code == 404

        # Org B attempts to list capabilities of Org A's Job -> 404
        get_b_resp = await client.get(
            f"/api/v1/jobs/{job_a_id}/capabilities",
            headers=auth_b["headers"],
        )
        assert get_b_resp.status_code == 404

        # Org B attempts to patch Org A's capability -> 404
        patch_b_resp = await client.patch(
            f"/api/v1/capabilities/{cap_a_id}",
            headers=auth_b["headers"],
            json={"name": "Hacked Name"},
        )
        assert patch_b_resp.status_code == 404

        # Org B attempts to delete Org A's capability -> 404
        del_b_resp = await client.delete(
            f"/api/v1/capabilities/{cap_a_id}",
            headers=auth_b["headers"],
        )
        assert del_b_resp.status_code == 404


@pytest.mark.asyncio
async def test_capability_input_validation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "Validation Job", "description": "Desc"},
        )
        job_id = job_resp.json()["id"]

        # Empty name
        resp1 = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": ""},
        )
        assert resp1.status_code == 422

        # Invalid importance enum
        resp2 = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": "Valid Name", "importance": "INVALID_IMPORTANCE"},
        )
        assert resp2.status_code == 422
