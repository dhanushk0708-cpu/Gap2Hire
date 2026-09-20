import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.interview import AIQuestionPayload
from tests.test_candidates_applications import create_registered_client
from tests.test_evidence_provenance import inject_provenance_evidence
from tests.test_evidence_summary import setup_summary_application


@pytest.mark.asyncio
async def test_create_interview_session():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, _ = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "Python", "description": "Lang"}],
        )

        res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers=auth["headers"],
        )
        assert res.status_code == 201
        data = res.json()
        assert data["application_id"] == app_id
        assert data["status"] == "CREATED"
        assert data["started_at"] is None


@pytest.mark.asyncio
async def test_cross_tenant_session_protection():
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

        create_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers=auth_company_1["headers"],
        )
        session_id = create_res.json()["id"]

        # Company 2 attempts access
        start_res = await client.patch(
            f"/api/v1/interviews/{session_id}/start",
            headers=auth_company_2["headers"],
        )
        assert start_res.status_code == 404

        next_q_res = await client.post(
            f"/api/v1/interviews/{session_id}/next-question",
            headers=auth_company_2["headers"],
        )
        assert next_q_res.status_code == 404


@pytest.mark.asyncio
async def test_start_interview_session():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, _ = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "Python", "description": "Lang"}],
        )

        create_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers=auth["headers"],
        )
        session_id = create_res.json()["id"]

        start_res = await client.patch(
            f"/api/v1/interviews/{session_id}/start",
            headers=auth["headers"],
        )
        assert start_res.status_code == 200
        data = start_res.json()
        assert data["status"] == "IN_PROGRESS"
        assert data["started_at"] is not None


@pytest.mark.asyncio
async def test_invalid_session_transition():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, _ = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "Python", "description": "Lang"}],
        )

        create_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers=auth["headers"],
        )
        session_id = create_res.json()["id"]

        # Start once
        await client.patch(
            f"/api/v1/interviews/{session_id}/start",
            headers=auth["headers"],
        )

        # Attempt starting again when IN_PROGRESS
        res = await client.patch(
            f"/api/v1/interviews/{session_id}/start",
            headers=auth["headers"],
        )
        assert res.status_code == 400


@pytest.mark.asyncio
@patch("app.services.interview.generate_interview_question")
async def test_next_question_targets_unresolved_capability(mock_ai_gen: AsyncMock):
    mock_ai_gen.return_value = AIQuestionPayload(
        question="Explain Redis caching strategies.",
        target_capability="Redis",
        reason="Resume has Redis CLAIM provenance without demonstration.",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[
                {"name": "Python", "description": "Language"},
                {"name": "Redis", "description": "Cache"},
            ],
        )

        # Inject DEMONSTRATED evidence for Python, but only CLAIM for Redis
        await inject_provenance_evidence(app_id, caps[0]["id"], "STRONG", "DEMONSTRATED", "Passed test")
        await inject_provenance_evidence(app_id, caps[1]["id"], "STRONG", "CLAIM", "Claims Redis expert")

        session_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers=auth["headers"],
        )
        session_id = session_res.json()["id"]

        await client.patch(
            f"/api/v1/interviews/{session_id}/start",
            headers=auth["headers"],
        )

        next_q_res = await client.post(
            f"/api/v1/interviews/{session_id}/next-question",
            headers=auth["headers"],
        )
        assert next_q_res.status_code == 200
        q_data = next_q_res.json()

        # Confirm target capability was Redis (unresolved CLAIM)
        assert q_data["capability_id"] == caps[1]["id"]
        assert q_data["question"] == "Explain Redis caching strategies."
        assert q_data["sequence_number"] == 1


@pytest.mark.asyncio
@patch("app.services.interview.generate_interview_question")
async def test_ai_response_validation_and_safety(mock_ai_gen: AsyncMock):
    mock_ai_gen.return_value = AIQuestionPayload(
        question="How do you handle connection pooling in FastAPI?",
        target_capability="FastAPI",
        reason="Targeting unresolved claim.",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "FastAPI", "description": "Framework"}],
        )

        session_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers=auth["headers"],
        )
        session_id = session_res.json()["id"]

        await client.patch(
            f"/api/v1/interviews/{session_id}/start",
            headers=auth["headers"],
        )

        res = await client.post(
            f"/api/v1/interviews/{session_id}/next-question",
            headers=auth["headers"],
        )
        assert res.status_code == 200
        data = res.json()
        assert "How do you handle connection pooling" in data["question"]


@pytest.mark.asyncio
@patch("app.services.interview.generate_interview_question")
async def test_submit_answer(mock_ai_gen: AsyncMock):
    mock_ai_gen.return_value = AIQuestionPayload(
        question="Describe AsyncIO event loop.",
        target_capability="Python",
        reason="Targeting CLAIM evidence.",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "Python", "description": "Language"}],
        )

        session_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers=auth["headers"],
        )
        session_id = session_res.json()["id"]

        await client.patch(
            f"/api/v1/interviews/{session_id}/start",
            headers=auth["headers"],
        )

        q_res = await client.post(
            f"/api/v1/interviews/{session_id}/next-question",
            headers=auth["headers"],
        )
        question_id = q_res.json()["id"]

        ans_res = await client.post(
            f"/api/v1/interviews/{session_id}/questions/{question_id}/answer",
            headers=auth["headers"],
            json={"answer": "AsyncIO runs an asynchronous event loop managing tasks concurrently."},
        )
        assert ans_res.status_code == 200
        ans_data = ans_res.json()
        assert ans_data["answer"] == "AsyncIO runs an asynchronous event loop managing tasks concurrently."

        # Fetch session detail and verify CANDIDATE message was stored
        detail_res = await client.get(
            f"/api/v1/interviews/{session_id}",
            headers=auth["headers"],
        )
        assert detail_res.status_code == 200
        messages = detail_res.json()["messages"]
        roles = [m["role"] for m in messages]
        assert "SYSTEM" in roles
        assert "AI" in roles
        assert "CANDIDATE" in roles


@pytest.mark.asyncio
@patch("app.services.interview.generate_interview_question")
async def test_duplicate_answer_rejected(mock_ai_gen: AsyncMock):
    mock_ai_gen.return_value = AIQuestionPayload(
        question="Describe Docker networking.",
        target_capability="Docker",
        reason="Targeting CLAIM evidence.",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "Docker", "description": "Containers"}],
        )

        session_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers=auth["headers"],
        )
        session_id = session_res.json()["id"]

        await client.patch(
            f"/api/v1/interviews/{session_id}/start",
            headers=auth["headers"],
        )

        q_res = await client.post(
            f"/api/v1/interviews/{session_id}/next-question",
            headers=auth["headers"],
        )
        question_id = q_res.json()["id"]

        # Submit answer first time
        await client.post(
            f"/api/v1/interviews/{session_id}/questions/{question_id}/answer",
            headers=auth["headers"],
            json={"answer": "Bridge network connects containers locally."},
        )

        # Submit answer second time -> expect 400
        dup_res = await client.post(
            f"/api/v1/interviews/{session_id}/questions/{question_id}/answer",
            headers=auth["headers"],
            json={"answer": "Submitting another answer."},
        )
        assert dup_res.status_code == 400
