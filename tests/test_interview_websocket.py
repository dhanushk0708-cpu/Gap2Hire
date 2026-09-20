import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.roles import UserRole
from app.db.session import async_session_factory
from app.main import app
from app.models.user import User
from app.schemas.interview_ws import WSAIMessageEvent


@pytest.fixture(scope="module")
def sync_client():
    with TestClient(app) as client:
        yield client


def create_sync_registered_client(client: TestClient):
    org_name = f"Test Company {uuid.uuid4()}"
    email = f"user-{uuid.uuid4()}@gap2hire.com"
    password = "TestPassword123!"

    response = client.post(
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

    me_resp = client.get(
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


def create_candidate_token_sync(client: TestClient):
    auth = create_sync_registered_client(client)
    user_id = auth["user_id"]

    async def _set_candidate_role():
        async with async_session_factory() as session:
            user = await session.get(User, uuid.UUID(user_id))
            user.role = UserRole.CANDIDATE.value
            await session.commit()

    client.portal.call(_set_candidate_role)
    return auth["token"]


def setup_session_sync(client: TestClient, caps=None):
    if caps is None:
        caps = [{"name": "Python", "description": "Lang"}]
    auth = create_sync_registered_client(client)
    headers = auth["headers"]

    job_resp = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "Backend Engineer", "description": "Python, FastAPI"},
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    created_caps = []
    for cap in caps:
        cap_resp = client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json=cap,
        )
        assert cap_resp.status_code == 201
        created_caps.append(cap_resp.json())

    cand_resp = client.post(
        "/api/v1/candidates",
        headers=headers,
        json={"full_name": "Test Candidate", "email": f"cand.{uuid.uuid4()}@example.com"},
    )
    assert cand_resp.status_code == 201
    candidate_id = cand_resp.json()["id"]

    app_resp = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"candidate_id": candidate_id, "job_id": job_id},
    )
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    create_res = client.post(
        f"/api/v1/applications/{app_id}/interviews",
        headers=headers,
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]

    return auth, app_id, session_id, created_caps


def test_authenticated_hr_can_connect(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)

    start_res = sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth["headers"],
    )
    assert start_res.status_code == 200

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        data = websocket.receive_json()
        assert data["type"] == "system"
        assert data["event"] == "connected"


def test_unauthenticated_connection_rejected(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)

    sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth["headers"],
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(
            f"/api/v1/interviews/{session_id}/ws"
        ):
            pass
    assert exc_info.value.code == 1008


def test_candidate_role_rejected(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    cand_token = create_candidate_token_sync(sync_client)

    sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth["headers"],
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(
            f"/api/v1/interviews/{session_id}/ws?token={cand_token}"
        ):
            pass
    assert exc_info.value.code == 1008


def test_cross_tenant_connection_rejected(sync_client):
    auth1, app_id, session_id, _ = setup_session_sync(sync_client)
    auth2 = create_sync_registered_client(sync_client)

    sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth1["headers"],
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(
            f"/api/v1/interviews/{session_id}/ws?token={auth2['token']}"
        ):
            pass
    assert exc_info.value.code == 1008


def test_non_in_progress_session_rejected(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(
            f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
        ):
            pass
    assert exc_info.value.code == 1008


def receive_next_non_avatar(ws):
    while True:
        data = ws.receive_json()
        if data.get("type") != "avatar_state":
            return data


@patch("app.api.interview_ws.process_live_candidate_message")
def test_candidate_message_and_ai_response_persisted(mock_process: AsyncMock, sync_client):
    mock_process.return_value = WSAIMessageEvent(
        content="Redis caching provides sub-millisecond data retrieval.",
        target_capability="Redis",
    )

    auth, app_id, session_id, _ = setup_session_sync(sync_client, [{"name": "Redis", "description": "Cache"}])

    sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth["headers"],
    )

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connection confirmation

        websocket.send_json({
            "type": "candidate_message",
            "content": "Tell me about Redis caching strategies.",
        })

        ai_msg = receive_next_non_avatar(websocket)
        assert ai_msg["type"] == "ai_message"
        assert "sub-millisecond" in ai_msg["content"]
        assert ai_msg["target_capability"] == "Redis"

    session_res = sync_client.get(
        f"/api/v1/interviews/{session_id}",
        headers=auth["headers"],
    )
    assert session_res.status_code == 200


def test_malformed_event_rejected(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)

    sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth["headers"],
    )

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connection message

        websocket.send_text("not_valid_json")

        err_msg = receive_next_non_avatar(websocket)
        assert err_msg["type"] == "system"
        assert err_msg["event"] == "error"
        assert "Malformed" in err_msg["content"]


def test_empty_candidate_message_rejected(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)

    sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth["headers"],
    )

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connection message

        websocket.send_json({
            "type": "candidate_message",
            "content": "   ",
        })

        err_msg = receive_next_non_avatar(websocket)
        assert err_msg["type"] == "system"
        assert err_msg["event"] == "error"
        assert "cannot be empty" in err_msg["content"].lower()


def test_second_connection_to_same_session_rejected(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)

    sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth["headers"],
    )

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as ws1:
        ws1.receive_json()  # connection confirmation

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with sync_client.websocket_connect(
                f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
            ):
                pass
        assert exc_info.value.code == 1008
