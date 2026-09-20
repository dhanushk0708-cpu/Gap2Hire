import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def sync_client():
    with TestClient(app) as client:
        yield client


def create_registered_hr(client: TestClient):
    org_name = f"Template Corp {uuid.uuid4()}"
    email = f"hr-{uuid.uuid4()}@templatecorp.com"
    password = "SecurePassword123!"

    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Template Manager",
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


def setup_round_with_capability(client: TestClient, auth: dict):
    # 1. Job
    j_res = client.post(
        "/api/v1/jobs",
        headers=auth["headers"],
        json={"title": "Cloud Architect", "description": "AWS & Kubernetes"},
    )
    assert j_res.status_code == 201
    job_id = j_res.json()["id"]

    # 2. Capability
    cap_res = client.post(
        f"/api/v1/jobs/{job_id}/capabilities",
        headers=auth["headers"],
        json={"name": "Kubernetes", "description": "Container orchestration", "importance": "HIGH"},
    )
    assert cap_res.status_code == 201
    cap_id = cap_res.json()["id"]

    # 3. Round
    r_res = client.post(
        f"/api/v1/jobs/{job_id}/interview-rounds",
        headers=auth["headers"],
        json={"name": "Architecture Round", "round_type": "TECHNICAL", "sequence": 1},
    )
    assert r_res.status_code == 201
    round_id = r_res.json()["id"]

    return job_id, cap_id, round_id


# 1. Create and list templates
def test_create_and_list_question_templates(sync_client):
    auth = create_registered_hr(sync_client)
    job_id, cap_id, round_id = setup_round_with_capability(sync_client, auth)

    # Create Template 1 (with capability)
    t1_res = sync_client.post(
        f"/api/v1/interview-rounds/{round_id}/question-templates",
        headers=auth["headers"],
        json={
            "capability_id": cap_id,
            "question_intent": "DEBUGGING",
            "question_text": "Describe how you would debug a CrashLoopBackOff state in a Pod.",
            "difficulty": "HARD",
            "required": True,
            "max_followups": 2,
            "sequence": 1,
        },
    )
    assert t1_res.status_code == 201
    t1 = t1_res.json()
    assert t1["capability_id"] == cap_id
    assert t1["question_intent"] == "DEBUGGING"
    assert t1["difficulty"] == "HARD"
    assert t1["max_followups"] == 2
    assert t1["sequence"] == 1

    # Create Template 2 (general, without capability)
    t2_res = sync_client.post(
        f"/api/v1/interview-rounds/{round_id}/question-templates",
        headers=auth["headers"],
        json={
            "question_intent": "EXPERIENCE",
            "question_text": "Tell me about a high-load architecture migration you led.",
            "difficulty": "MEDIUM",
            "required": True,
            "max_followups": 1,
            "sequence": 2,
        },
    )
    assert t2_res.status_code == 201
    t2 = t2_res.json()
    assert t2["capability_id"] is None
    assert t2["sequence"] == 2

    # List templates
    list_res = sync_client.get(
        f"/api/v1/interview-rounds/{round_id}/question-templates",
        headers=auth["headers"],
    )
    assert list_res.status_code == 200
    templates = list_res.json()
    assert len(templates) == 2
    assert templates[0]["sequence"] == 1
    assert templates[1]["sequence"] == 2


# 2. Sequence uniqueness in round
def test_duplicate_template_sequence_rejected(sync_client):
    auth = create_registered_hr(sync_client)
    job_id, cap_id, round_id = setup_round_with_capability(sync_client, auth)

    sync_client.post(
        f"/api/v1/interview-rounds/{round_id}/question-templates",
        headers=auth["headers"],
        json={"question_intent": "KNOWLEDGE", "question_text": "Question 1", "sequence": 1},
    )

    dup_res = sync_client.post(
        f"/api/v1/interview-rounds/{round_id}/question-templates",
        headers=auth["headers"],
        json={"question_intent": "KNOWLEDGE", "question_text": "Question 2", "sequence": 1},
    )
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()


# 3. Invalid capability matching rejected
def test_invalid_capability_for_job_rejected(sync_client):
    auth1 = create_registered_hr(sync_client)
    auth2 = create_registered_hr(sync_client)
    job_id, cap_id1, round_id = setup_round_with_capability(sync_client, auth1)
    _, cap_id2, _ = setup_round_with_capability(sync_client, auth2)

    # Attempt to assign auth2's capability to auth1's round template
    mismatch_res = sync_client.post(
        f"/api/v1/interview-rounds/{round_id}/question-templates",
        headers=auth1["headers"],
        json={
            "capability_id": cap_id2,
            "question_intent": "KNOWLEDGE",
            "question_text": "Mismatched capability question",
            "sequence": 1,
        },
    )
    assert mismatch_res.status_code == 400
    assert "does not belong" in mismatch_res.json()["detail"].lower()


# 4. Update and delete template
def test_update_and_delete_template(sync_client):
    auth = create_registered_hr(sync_client)
    job_id, cap_id, round_id = setup_round_with_capability(sync_client, auth)

    t_res = sync_client.post(
        f"/api/v1/interview-rounds/{round_id}/question-templates",
        headers=auth["headers"],
        json={"question_intent": "KNOWLEDGE", "question_text": "Initial template text", "sequence": 1},
    )
    template_id = t_res.json()["id"]

    # Update
    patch_res = sync_client.patch(
        f"/api/v1/interview-question-templates/{template_id}",
        headers=auth["headers"],
        json={"question_text": "Updated template text", "difficulty": "HARD", "max_followups": 3},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["question_text"] == "Updated template text"
    assert patch_res.json()["difficulty"] == "HARD"
    assert patch_res.json()["max_followups"] == 3

    # Delete
    del_res = sync_client.delete(
        f"/api/v1/interview-question-templates/{template_id}",
        headers=auth["headers"],
    )
    assert del_res.status_code == 204

    # Update on deleted template returns 404
    patch_after = sync_client.patch(
        f"/api/v1/interview-question-templates/{template_id}",
        headers=auth["headers"],
        json={"question_text": "Should 404"},
    )
    assert patch_after.status_code == 404
