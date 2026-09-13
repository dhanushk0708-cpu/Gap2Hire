import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.roles import UserRole
from app.core.security import create_access_token, hash_password
from app.db.session import async_session_factory
from app.main import app
from app.models.user import User


async def create_registered_client(client: AsyncClient):
    org_name = f"Test Company {uuid.uuid4()}"
    email = f"user-{uuid.uuid4()}@gap2hire.com"
    password = "TestPassword123!"

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test Manager",
            "organization_name": org_name,
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]

    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    user_data = me_resp.json()

    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_data["id"],
        "organization_id": user_data["organization_id"],
    }


@pytest.mark.asyncio
async def test_job_crud_authorized_flow():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        # 1. Create Job
        create_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "title": "Software Engineer",
                "description": "Develop scalable Python microservices and APIs.",
                "status": "DRAFT",
            },
        )
        assert create_resp.status_code == 201
        job = create_resp.json()
        job_id = job["id"]

        assert job["title"] == "Software Engineer"
        assert job["description"] == "Develop scalable Python microservices and APIs."
        assert job["status"] == "DRAFT"
        assert job["organization_id"] == auth["organization_id"]
        assert job["created_by"] == auth["user_id"]
        assert "created_at" in job
        assert "updated_at" in job

        # 2. List Jobs
        list_resp = await client.get(
            "/api/v1/jobs",
            headers=headers,
        )
        assert list_resp.status_code == 200
        jobs_list = list_resp.json()
        assert len(jobs_list) >= 1
        assert any(j["id"] == job_id for j in jobs_list)

        # 3. Get Job
        get_resp = await client.get(
            f"/api/v1/jobs/{job_id}",
            headers=headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == job_id

        # 4. Update Job
        update_resp = await client.patch(
            f"/api/v1/jobs/{job_id}",
            headers=headers,
            json={
                "title": "Senior Software Engineer",
                "status": "ACTIVE",
            },
        )
        assert update_resp.status_code == 200
        updated_job = update_resp.json()
        assert updated_job["title"] == "Senior Software Engineer"
        assert updated_job["status"] == "ACTIVE"
        assert updated_job["description"] == "Develop scalable Python microservices and APIs."

        # 5. Delete Job
        delete_resp = await client.delete(
            f"/api/v1/jobs/{job_id}",
            headers=headers,
        )
        assert delete_resp.status_code == 204

        # Verify Job deleted
        get_after_delete = await client.get(
            f"/api/v1/jobs/{job_id}",
            headers=headers,
        )
        assert get_after_delete.status_code == 404


@pytest.mark.asyncio
async def test_job_unauthenticated_access_rejected():
    fake_job_id = str(uuid.uuid4())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # No Authorization headers
        post_resp = await client.post(
            "/api/v1/jobs",
            json={"title": "Test", "description": "Test Desc"},
        )
        assert post_resp.status_code in (401, 403)

        get_list_resp = await client.get("/api/v1/jobs")
        assert get_list_resp.status_code in (401, 403)

        get_resp = await client.get(f"/api/v1/jobs/{fake_job_id}")
        assert get_resp.status_code in (401, 403)

        patch_resp = await client.patch(
            f"/api/v1/jobs/{fake_job_id}",
            json={"title": "Updated"},
        )
        assert patch_resp.status_code in (401, 403)

        delete_resp = await client.delete(f"/api/v1/jobs/{fake_job_id}")
        assert delete_resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_candidate_cannot_manage_jobs():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        org_id = uuid.UUID(auth["organization_id"])

        # Insert a candidate user into the same org
        candidate_email = f"candidate-{uuid.uuid4()}@gap2hire.com"
        candidate_user = User(
            organization_id=org_id,
            email=candidate_email,
            password_hash=hash_password("CandidatePass123!"),
            full_name="Candidate Person",
            role=UserRole.CANDIDATE.value,
        )

        async with async_session_factory() as session:
            session.add(candidate_user)
            await session.commit()
            await session.refresh(candidate_user)
            candidate_id = candidate_user.id

        candidate_token = create_access_token(str(candidate_id))
        candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

        # Candidate attempts to create a job -> 403
        post_resp = await client.post(
            "/api/v1/jobs",
            headers=candidate_headers,
            json={"title": "Job Title", "description": "Job Description"},
        )
        assert post_resp.status_code == 403

        # Candidate attempts to list jobs -> 403
        list_resp = await client.get(
            "/api/v1/jobs",
            headers=candidate_headers,
        )
        assert list_resp.status_code == 403


@pytest.mark.asyncio
async def test_cross_organization_job_isolation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_org_a = await create_registered_client(client)
        auth_org_b = await create_registered_client(client)

        # Org A creates a job
        create_resp = await client.post(
            "/api/v1/jobs",
            headers=auth_org_a["headers"],
            json={
                "title": "Org A Secret Job",
                "description": "Confidential details for Org A only.",
            },
        )
        assert create_resp.status_code == 201
        job_a_id = create_resp.json()["id"]

        # Org B lists jobs -> must not see Org A's job
        list_resp_b = await client.get(
            "/api/v1/jobs",
            headers=auth_org_b["headers"],
        )
        assert list_resp_b.status_code == 200
        jobs_b = list_resp_b.json()
        assert not any(j["id"] == job_a_id for j in jobs_b)

        # Org B tries to get Org A's job directly -> 404
        get_resp_b = await client.get(
            f"/api/v1/jobs/{job_a_id}",
            headers=auth_org_b["headers"],
        )
        assert get_resp_b.status_code == 404

        # Org B tries to patch Org A's job -> 404
        patch_resp_b = await client.patch(
            f"/api/v1/jobs/{job_a_id}",
            headers=auth_org_b["headers"],
            json={"title": "Hacked Title"},
        )
        assert patch_resp_b.status_code == 404

        # Org B tries to delete Org A's job -> 404
        delete_resp_b = await client.delete(
            f"/api/v1/jobs/{job_a_id}",
            headers=auth_org_b["headers"],
        )
        assert delete_resp_b.status_code == 404


@pytest.mark.asyncio
async def test_job_input_validation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        # Empty title
        resp1 = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "", "description": "Some description"},
        )
        assert resp1.status_code == 422

        # Empty description
        resp2 = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "Valid Title", "description": ""},
        )
        assert resp2.status_code == 422

        # Invalid status enum
        resp3 = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "title": "Valid Title",
                "description": "Valid Description",
                "status": "NON_EXISTENT_STATUS",
            },
        )
        assert resp3.status_code == 422
