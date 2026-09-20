import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.roles import UserRole
from app.db.session import async_session_factory
from app.main import app
from app.models.user import User


@pytest.fixture(scope="module")
def sync_client():
    with TestClient(app) as client:
        yield client


def create_registered_hr(client: TestClient):
    org_name = f"Round Corp {uuid.uuid4()}"
    email = f"hr-{uuid.uuid4()}@roundcorp.com"
    password = "SecurePassword123!"

    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Round Manager",
            "organization_name": org_name,
        },
    )
    assert res.status_code == 201
    token = res.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": me["id"],
        "organization_id": me["organization_id"],
    }


def create_candidate_user(client: TestClient):
    auth = create_registered_hr(client)
    user_id = auth["user_id"]

    async def _demote():
        async with async_session_factory() as s:
            user = await s.get(User, uuid.UUID(user_id))
            user.role = UserRole.CANDIDATE.value
            await s.commit()

    client.portal.call(_demote)
    return auth


def create_test_job(client: TestClient, headers: dict):
    res = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "Backend Lead", "description": "FastAPI & Python"},
    )
    assert res.status_code == 201
    return res.json()["id"]


# 1. Create round and list rounds
def test_create_and_list_interview_rounds(sync_client):
    auth = create_registered_hr(sync_client)
    job_id = create_test_job(sync_client, auth["headers"])

    # Create Round 1
    r1_res = sync_client.post(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=auth["headers"],
        json={
            "name": "HR Screening",
            "round_type": "HR_SCREENING",
            "sequence": 1,
            "description": "Cultural and background discussion",
        },
    )
    assert r1_res.status_code == 201
    r1 = r1_res.json()
    assert r1["name"] == "HR Screening"
    assert r1["round_type"] == "HR_SCREENING"
    assert r1["sequence"] == 1

    # Create Round 2
    r2_res = sync_client.post(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=auth["headers"],
        json={
            "name": "Technical Deep Dive",
            "round_type": "TECHNICAL",
            "sequence": 2,
            "description": "Core architecture and coding",
        },
    )
    assert r2_res.status_code == 201

    # List rounds
    list_res = sync_client.get(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=auth["headers"],
    )
    assert list_res.status_code == 200
    rounds = list_res.json()
    assert len(rounds) == 2
    assert rounds[0]["sequence"] == 1
    assert rounds[1]["sequence"] == 2


# 2. Sequence uniqueness enforcement
def test_round_duplicate_sequence_rejected(sync_client):
    auth = create_registered_hr(sync_client)
    job_id = create_test_job(sync_client, auth["headers"])

    sync_client.post(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=auth["headers"],
        json={"name": "Round A", "round_type": "HR_SCREENING", "sequence": 1},
    )

    dup_res = sync_client.post(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=auth["headers"],
        json={"name": "Round B", "round_type": "TECHNICAL", "sequence": 1},
    )
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()


# 3. Update and delete round
def test_update_and_delete_round(sync_client):
    auth = create_registered_hr(sync_client)
    job_id = create_test_job(sync_client, auth["headers"])

    r_res = sync_client.post(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=auth["headers"],
        json={"name": "Initial Name", "round_type": "TECHNICAL", "sequence": 1},
    )
    round_id = r_res.json()["id"]

    # Update
    patch_res = sync_client.patch(
        f"/api/v1/interview-rounds/{round_id}",
        headers=auth["headers"],
        json={"name": "Updated Name", "round_type": "PRACTICAL"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Updated Name"
    assert patch_res.json()["round_type"] == "PRACTICAL"

    # Detail
    get_res = sync_client.get(
        f"/api/v1/interview-rounds/{round_id}",
        headers=auth["headers"],
    )
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Updated Name"

    # Delete
    del_res = sync_client.delete(
        f"/api/v1/interview-rounds/{round_id}",
        headers=auth["headers"],
    )
    assert del_res.status_code == 204

    # Confirm 404
    get_after = sync_client.get(
        f"/api/v1/interview-rounds/{round_id}",
        headers=auth["headers"],
    )
    assert get_after.status_code == 404


# 4. Tenant isolation and authorization
def test_rounds_tenant_isolation_and_role_protection(sync_client):
    auth1 = create_registered_hr(sync_client)
    auth2 = create_registered_hr(sync_client)
    cand_auth = create_candidate_user(sync_client)

    job_id = create_test_job(sync_client, auth1["headers"])

    # Candidate forbidden
    cand_res = sync_client.post(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=cand_auth["headers"],
        json={"name": "Forbidden Round", "sequence": 1},
    )
    assert cand_res.status_code == 403

    # Cross-tenant forbidden / 404
    cross_res = sync_client.post(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=auth2["headers"],
        json={"name": "Cross Tenant Round", "sequence": 1},
    )
    assert cross_res.status_code == 404
