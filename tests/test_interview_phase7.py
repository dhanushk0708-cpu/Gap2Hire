import base64
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.roles import UserRole
from app.core.security import create_access_token
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.schemas.interview_avatar import AvatarState
from app.schemas.interview_ws import WSAIMessageEvent
from app.services.interview_ws_manager import connection_manager


@pytest.fixture(autouse=True)
def cleanup_connections():
    """Ensure WebSocket connection manager is cleared between tests."""
    connection_manager.active_connections.clear()
    connection_manager.rate_limiter.timestamps.clear()
    yield
    connection_manager.active_connections.clear()
    connection_manager.rate_limiter.timestamps.clear()


@pytest.fixture(scope="module")
def sync_client():
    with TestClient(app) as client:
        yield client


def build_mock_session_and_users():
    org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    app_id = uuid.uuid4()
    session_id = uuid.uuid4()
    cand_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    manager_user_id = uuid.uuid4()

    cand_email = f"candidate.{cand_id.hex[:6]}@example.com"
    other_email = f"unauthorized.{other_user_id.hex[:6]}@example.com"
    manager_email = f"recruiter.{manager_user_id.hex[:6]}@example.com"

    # Models
    candidate = Candidate(
        id=cand_id,
        full_name="Phase7 Live Candidate",
        email=cand_email,
    )
    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Senior AI Systems Engineer",
        description="FastAPI, WebSockets",
    )
    application = Application(
        id=app_id,
        candidate_id=cand_id,
        job_id=job_id,
        candidate=candidate,
        job=job,
    )
    interview_session = InterviewSession(
        id=session_id,
        application_id=app_id,
        status="IN_PROGRESS",
        application=application,
        questions=[],
        messages=[],
    )

    # Users
    candidate_user = User(
        id=cand_user_id,
        organization_id=org_id,
        email=cand_email,
        full_name="Phase7 Live Candidate",
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )
    other_candidate_user = User(
        id=other_user_id,
        organization_id=org_id,
        email=other_email,
        full_name="Other Candidate",
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )
    manager_user = User(
        id=manager_user_id,
        organization_id=org_id,
        email=manager_email,
        full_name="Hiring Manager",
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )

    # Tokens
    cand_token = create_access_token(str(cand_user_id))
    other_token = create_access_token(str(other_user_id))
    manager_token = create_access_token(str(manager_user_id))

    return {
        "org_id": org_id,
        "session_id": session_id,
        "interview_session": interview_session,
        "cand_user": candidate_user,
        "other_user": other_candidate_user,
        "manager_user": manager_user,
        "cand_token": cand_token,
        "other_token": other_token,
        "manager_token": manager_token,
    }


# --------------------------------------------------------------------------
# Test 1: Candidate can access live interview room for their own session
# --------------------------------------------------------------------------
def test_candidate_access_authorized_live_room(sync_client):
    data = build_mock_session_and_users()
    session_id = data["session_id"]

    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]

    async def mock_get_db():
        yield mock_db

    from app.api.dependencies import get_current_user
    from app.db.session import get_db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: data["cand_user"]

    try:
        response = sync_client.get(
            f"/api/v1/interviews/{session_id}/room",
            headers={"Authorization": f"Bearer {data['cand_token']}"},
        )
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["session_id"] == str(session_id)
        assert res_data["status"] == "IN_PROGRESS"
        assert res_data["candidate_name"] == "Phase7 Live Candidate"
        assert res_data["ws_path"] == f"/api/v1/interviews/{session_id}/ws"
        assert res_data["avatar"]["display_name"] == "AI Interviewer"
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------
# Test 2: Candidate accessing another candidate's session is rejected (403)
# --------------------------------------------------------------------------
def test_candidate_access_unauthorized_live_room_rejected(sync_client):
    data = build_mock_session_and_users()
    session_id = data["session_id"]

    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]

    async def mock_get_db():
        yield mock_db

    from app.api.dependencies import get_current_user
    from app.db.session import get_db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: data["other_user"]

    try:
        response = sync_client.get(
            f"/api/v1/interviews/{session_id}/room",
            headers={"Authorization": f"Bearer {data['other_token']}"},
        )
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------
# Test 3: WebSocket connection authenticates candidate and returns IDLE state
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
def test_websocket_candidate_connection_authorized(mock_db_factory, mock_auth_ws, sync_client):
    data = build_mock_session_and_users()
    session_id = data["session_id"]

    mock_auth_ws.return_value = data["cand_user"]

    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={data['cand_token']}"
    ) as ws:
        # Initial system confirmation
        sys_event = ws.receive_json()
        assert sys_event["type"] == "system"
        assert sys_event["event"] == "connected"

        # Initial Avatar IDLE state
        avatar_event = ws.receive_json()
        assert avatar_event["type"] == "avatar_state"
        assert avatar_event["state"] == AvatarState.IDLE.value


# --------------------------------------------------------------------------
# Test 4: Unauthorized candidate WebSocket connection is closed
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
def test_websocket_candidate_connection_unauthorized_rejected(mock_db_factory, mock_auth_ws, sync_client):
    data = build_mock_session_and_users()
    session_id = data["session_id"]

    mock_auth_ws.return_value = data["other_user"]

    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    with pytest.raises(Exception):
        with sync_client.websocket_connect(
            f"/api/v1/interviews/{session_id}/ws?token={data['other_token']}"
        ) as ws:
            ws.receive_json()


# --------------------------------------------------------------------------
# Test 5: Candidate message payload triggers THINKING -> SPEAKING -> IDLE flow
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
@patch("app.api.interview_ws.process_live_candidate_message")
def test_websocket_avatar_state_transitions_text_message(
    mock_process: AsyncMock,
    mock_db_factory,
    mock_auth_ws,
    sync_client,
):
    data = build_mock_session_and_users()
    session_id = data["session_id"]

    mock_auth_ws.return_value = data["cand_user"]
    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    mock_process.return_value = WSAIMessageEvent(
        content="Explain how WebSocket heartbeats prevent connection timeout.",
        target_capability="FastAPI WebSockets",
    )

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={data['cand_token']}"
    ) as ws:
        ws.receive_json()  # system connected
        ws.receive_json()  # avatar IDLE

        # Candidate sends text response
        ws.send_json({
            "type": "candidate_message",
            "content": "I use periodic ping/pong frames every 30 seconds.",
        })

        # 1. Avatar transitions to THINKING
        evt_thinking = ws.receive_json()
        assert evt_thinking["type"] == "avatar_state"
        assert evt_thinking["state"] == AvatarState.THINKING.value

        # 2. Avatar transitions to SPEAKING
        evt_speaking = ws.receive_json()
        assert evt_speaking["type"] == "avatar_state"
        assert evt_speaking["state"] == AvatarState.SPEAKING.value

        # 3. AI Message response
        evt_ai_msg = ws.receive_json()
        assert evt_ai_msg["type"] == "ai_message"
        assert "WebSocket heartbeats" in evt_ai_msg["content"]

        # 4. Avatar returns to IDLE
        evt_idle = ws.receive_json()
        assert evt_idle["type"] == "avatar_state"
        assert evt_idle["state"] == AvatarState.IDLE.value


# --------------------------------------------------------------------------
# Test 6: Voice audio payload transitions LISTENING -> THINKING -> SPEAKING -> IDLE
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
@patch("app.api.interview_ws.get_stt_service")
@patch("app.api.interview_ws.process_live_candidate_message")
@patch("app.api.interview_ws.get_tts_service")
def test_websocket_avatar_state_transitions_voice_audio(
    mock_get_tts,
    mock_process_msg: AsyncMock,
    mock_get_stt,
    mock_db_factory,
    mock_auth_ws,
    sync_client,
):
    data = build_mock_session_and_users()
    session_id = data["session_id"]

    mock_auth_ws.return_value = data["cand_user"]
    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = "I configure connection pools and timeout retry policies."
    mock_get_stt.return_value = mock_stt

    mock_process_msg.return_value = WSAIMessageEvent(
        content="Great! How do you handle deadlocks in database transactions?",
        target_capability="FastAPI WebSockets",
    )

    mock_tts = AsyncMock()
    mock_tts.synthesize.return_value = b"\x00\x01\x02\x03\x04FAKE_AUDIO_MP3"
    mock_get_tts.return_value = mock_tts

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={data['cand_token']}"
    ) as ws:
        ws.receive_json()  # system connected
        ws.receive_json()  # avatar IDLE

        fake_audio_b64 = base64.b64encode(b"RIFF....WAVEfmt ....dataFAKEPCM").decode("utf-8")

        # Candidate sends voice audio payload
        ws.send_json({
            "type": "candidate_audio",
            "audio": fake_audio_b64,
            "content_type": "audio/webm",
        })

        # 1. Avatar enters LISTENING
        e1 = ws.receive_json()
        assert e1["type"] == "avatar_state"
        assert e1["state"] == AvatarState.LISTENING.value

        # 2. Transcript event
        e2 = ws.receive_json()
        assert e2["type"] == "transcript"
        assert e2["role"] == "candidate"
        assert "connection pools" in e2["content"]

        # 3. Avatar enters THINKING
        e3 = ws.receive_json()
        assert e3["type"] == "avatar_state"
        assert e3["state"] == AvatarState.THINKING.value

        # 4. Avatar enters SPEAKING
        e4 = ws.receive_json()
        assert e4["type"] == "avatar_state"
        assert e4["state"] == AvatarState.SPEAKING.value

        # 5. AI text response
        e5 = ws.receive_json()
        assert e5["type"] == "ai_message"
        assert "deadlocks" in e5["content"]

        # 6. AI audio synthesized response
        e6 = ws.receive_json()
        assert e6["type"] == "ai_audio"
        assert e6["content_type"] == "audio/mpeg"

        # 7. Avatar returns to IDLE
        e7 = ws.receive_json()
        assert e7["type"] == "avatar_state"
        assert e7["state"] == AvatarState.IDLE.value


# --------------------------------------------------------------------------
# Test 7: Malformed and empty payloads return graceful error events
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
def test_websocket_malformed_and_empty_payload_error_handling(mock_db_factory, mock_auth_ws, sync_client):
    data = build_mock_session_and_users()
    session_id = data["session_id"]

    mock_auth_ws.return_value = data["cand_user"]
    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={data['cand_token']}"
    ) as ws:
        ws.receive_json()  # system connected
        ws.receive_json()  # avatar IDLE

        # A. Send malformed non-JSON text
        ws.send_text("NOT_VALID_JSON_STRING{{{")
        err1 = ws.receive_json()
        assert err1["type"] == "system"
        assert err1["event"] == "error"
        assert "malformed" in err1["content"].lower()

        # B. Send empty candidate message
        ws.send_json({
            "type": "candidate_message",
            "content": "   ",
        })
        err2 = ws.receive_json()
        assert err2["type"] == "system"
        assert err2["event"] == "error"
        assert "empty" in err2["content"].lower()


# --------------------------------------------------------------------------
# Test 8: Duplicate WebSocket connections on same session are rejected & cleanup frees slot
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
def test_websocket_duplicate_connection_rejected_and_disconnect_cleanup(mock_db_factory, mock_auth_ws, sync_client):
    data = build_mock_session_and_users()
    session_id = data["session_id"]

    mock_auth_ws.return_value = data["cand_user"]
    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    # First connection succeeds
    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={data['cand_token']}"
    ) as ws1:
        ws1.receive_json()  # system connected
        ws1.receive_json()  # avatar IDLE

        # Second concurrent connection to same session is rejected
        with pytest.raises(Exception):
            with sync_client.websocket_connect(
                f"/api/v1/interviews/{session_id}/ws?token={data['cand_token']}"
            ) as ws2:
                ws2.receive_json()

    # After ws1 context exits and disconnects, a new connection can connect cleanly
    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={data['cand_token']}"
    ) as ws3:
        sys_msg = ws3.receive_json()
        assert sys_msg["type"] == "system"
        assert sys_msg["event"] == "connected"
