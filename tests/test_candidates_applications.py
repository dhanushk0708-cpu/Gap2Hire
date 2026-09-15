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


async def create_candidate_user(organization_id: str):
    email = f"candidate-{uuid.uuid4()}@gap2hire.com"
    hashed = hash_password("CandidatePass123!")

    async with async_session_factory() as session:
        user = User(
            email=email,
            password_hash=hashed,
            full_name="Candidate User",
            role=UserRole.CANDIDATE.value,
            organization_id=uuid.UUID(organization_id),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(user_id=str(user_id))
    return {"headers": {"Authorization": f"Bearer {token}"}}


@pytest.mark.asyncio
async def test_candidate_crud_flow():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        # 1. Create Candidate
        create_resp = await client.post(
            "/api/v1/candidates",
            headers=headers,
            json={
                "full_name": "Jane Doe",
                "email": f"jane.doe.{uuid.uuid4()}@example.com",
                "phone": "+1234567890",
            },
        )
        assert create_resp.status_code == 201
        candidate_data = create_resp.json()
        candidate_id = candidate_data["id"]
        assert candidate_data["full_name"] == "Jane Doe"
        assert candidate_data["phone"] == "+1234567890"

        # 2. Get Candidate
        get_resp = await client.get(
            f"/api/v1/candidates/{candidate_id}",
            headers=headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == candidate_id

        # 3. Update Candidate
        update_resp = await client.patch(
            f"/api/v1/candidates/{candidate_id}",
            headers=headers,
            json={"full_name": "Jane Smith-Doe", "phone": "+9876543210"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["full_name"] == "Jane Smith-Doe"
        assert update_resp.json()["phone"] == "+9876543210"


@pytest.mark.asyncio
async def test_application_creation_retrieval_and_update_flow():
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
                "title": "Backend Developer",
                "description": "Python, FastAPI, Postgres",
                "status": "ACTIVE",
            },
        )
        assert job_resp.status_code == 201
        job_id = job_resp.json()["id"]

        # Create Candidate
        cand_resp = await client.post(
            "/api/v1/candidates",
            headers=headers,
            json={
                "full_name": "Alice Johnson",
                "email": f"alice.{uuid.uuid4()}@example.com",
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
                "status": "APPLIED",
                "resume_path": "/uploads/resumes/alice_resume.pdf",
            },
        )
        assert app_resp.status_code == 201
        app_data = app_resp.json()
        app_id = app_data["id"]
        assert app_data["candidate_id"] == candidate_id
        assert app_data["job_id"] == job_id
        assert app_data["status"] == "APPLIED"

        # List Applications
        list_resp = await client.get("/api/v1/applications", headers=headers)
        assert list_resp.status_code == 200
        apps = list_resp.json()
        assert len(apps) >= 1
        assert any(a["id"] == app_id for a in apps)

        # Get Application by ID
        get_app_resp = await client.get(
            f"/api/v1/applications/{app_id}",
            headers=headers,
        )
        assert get_app_resp.status_code == 200
        assert get_app_resp.json()["id"] == app_id

        # Update Application Status
        patch_app_resp = await client.patch(
            f"/api/v1/applications/{app_id}",
            headers=headers,
            json={"status": "IN_REVIEW"},
        )
        assert patch_app_resp.status_code == 200
        assert patch_app_resp.json()["status"] == "IN_REVIEW"


@pytest.mark.asyncio
async def test_duplicate_application_protection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "DevOps Engineer", "description": "CI/CD & Kubernetes"},
        )
        job_id = job_resp.json()["id"]

        cand_resp = await client.post(
            "/api/v1/candidates",
            headers=headers,
            json={"full_name": "Bob Vance", "email": f"bob.{uuid.uuid4()}@example.com"},
        )
        candidate_id = cand_resp.json()["id"]

        # First application succeeds
        app_resp1 = await client.post(
            "/api/v1/applications",
            headers=headers,
            json={"candidate_id": candidate_id, "job_id": job_id},
        )
        assert app_resp1.status_code == 201

        # Duplicate application returns 409 Conflict
        app_resp2 = await client.post(
            "/api/v1/applications",
            headers=headers,
            json={"candidate_id": candidate_id, "job_id": job_id},
        )
        assert app_resp2.status_code == 409
        assert "already applied" in app_resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_job_or_candidate_handling():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "QA Engineer", "description": "Testing"},
        )
        valid_job_id = job_resp.json()["id"]

        cand_resp = await client.post(
            "/api/v1/candidates",
            headers=headers,
            json={"full_name": "Charlie", "email": f"charlie.{uuid.uuid4()}@example.com"},
        )
        valid_cand_id = cand_resp.json()["id"]

        fake_id = str(uuid.uuid4())

        # Non-existent candidate
        res1 = await client.post(
            "/api/v1/applications",
            headers=headers,
            json={"candidate_id": fake_id, "job_id": valid_job_id},
        )
        assert res1.status_code == 404
        assert "candidate" in res1.json()["detail"].lower()

        # Non-existent job
        res2 = await client.post(
            "/api/v1/applications",
            headers=headers,
            json={"candidate_id": valid_cand_id, "job_id": fake_id},
        )
        assert res2.status_code == 404
        assert "job" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Candidate endpoints unauthenticated
        res1 = await client.post(
            "/api/v1/candidates",
            json={"full_name": "No Auth", "email": "noauth@example.com"},
        )
        assert res1.status_code == 401

        res2 = await client.get(f"/api/v1/candidates/{uuid.uuid4()}")
        assert res2.status_code == 401

        # Application endpoints unauthenticated
        res3 = await client.post(
            "/api/v1/applications",
            json={"candidate_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4())},
        )
        assert res3.status_code == 401

        res4 = await client.get("/api/v1/applications")
        assert res4.status_code == 401


@pytest.mark.asyncio
async def test_candidate_role_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        cand_auth = await create_candidate_user(auth["organization_id"])
        cand_headers = cand_auth["headers"]

        # Candidate user tries to create candidate -> 403
        res1 = await client.post(
            "/api/v1/candidates",
            headers=cand_headers,
            json={"full_name": "Test", "email": "test@example.com"},
        )
        assert res1.status_code == 403

        # Candidate user tries to list applications -> 403
        res2 = await client.get("/api/v1/applications", headers=cand_headers)
        assert res2.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_isolation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_company_1 = await create_registered_client(client)
        auth_company_2 = await create_registered_client(client)

        # Company 1 creates Job and Candidate and Application
        job1_resp = await client.post(
            "/api/v1/jobs",
            headers=auth_company_1["headers"],
            json={"title": "Org 1 Job", "description": "Company 1 only"},
        )
        job1_id = job1_resp.json()["id"]

        cand1_resp = await client.post(
            "/api/v1/candidates",
            headers=auth_company_1["headers"],
            json={"full_name": "Org1 Candidate", "email": f"org1.{uuid.uuid4()}@example.com"},
        )
        cand1_id = cand1_resp.json()["id"]

        app1_resp = await client.post(
            "/api/v1/applications",
            headers=auth_company_1["headers"],
            json={"candidate_id": cand1_id, "job_id": job1_id},
        )
        app1_id = app1_resp.json()["id"]

        # Company 2 tries to apply candidate to Company 1's job -> 404 (Job not found for Org 2)
        cross_app_resp = await client.post(
            "/api/v1/applications",
            headers=auth_company_2["headers"],
            json={"candidate_id": cand1_id, "job_id": job1_id},
        )
        assert cross_app_resp.status_code == 404

        # Company 2 tries to GET Company 1's Application -> 404
        get_app_cross = await client.get(
            f"/api/v1/applications/{app1_id}",
            headers=auth_company_2["headers"],
        )
        assert get_app_cross.status_code == 404

        # Company 2 tries to GET Company 1's Candidate (which has application in Org 1 only) -> 404
        get_cand_cross = await client.get(
            f"/api/v1/candidates/{cand1_id}",
            headers=auth_company_2["headers"],
        )
        assert get_cand_cross.status_code == 404

        # Company 2 tries to PATCH Company 1's Application -> 404
        patch_app_cross = await client.patch(
            f"/api/v1/applications/{app1_id}",
            headers=auth_company_2["headers"],
            json={"status": "REJECTED"},
        )
        assert patch_app_cross.status_code == 404
