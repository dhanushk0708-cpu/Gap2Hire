import base64
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.roles import UserRole
from app.db.session import async_session_factory
from app.main import app
from app.models.user import User
from app.schemas.interview_avatar import AvatarState, InterviewAvatarMetadata, WSAvatarStateEvent
from app.schemas.interview_ws import WSAIMessageEvent
from app.services.speech_to_text import SpeechToTextError
from app.services.text_to_speech import TextToSpeechError


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


def setup_session_sync(client: TestClient, caps=None):
    if caps is None:
        caps = [{"name": "System Architecture", "description": "Design distributed systems"}]
    auth = create_sync_registered_client(client)
    headers = auth["headers"]

    job_resp = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "Principal Architect", "description": "Cloud, Distributed Systems"},
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
        json={"full_name": "Avatar Candidate", "email": f"cand.{uuid.uuid4()}@example.com"},
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


# 1. Avatar state schema validation
def test_avatar_state_schema():
    assert AvatarState.IDLE.value == "IDLE"
    assert AvatarState.LISTENING.value == "LISTENING"
    assert AvatarState.THINKING.value == "THINKING"
    assert AvatarState.SPEAKING.value == "SPEAKING"
    assert AvatarState.ERROR.value == "ERROR"

    event = WSAvatarStateEvent(state=AvatarState.THINKING)
    assert event.type == "avatar_state"
    assert event.state == AvatarState.THINKING

    metadata = InterviewAvatarMetadata()
    assert metadata.avatar_id == "default-interviewer"
    assert metadata.voice_enabled is True
    assert metadata.avatar_enabled is True

    with pytest.raises(ValidationError):
        WSAvatarStateEvent.model_validate({"type": "avatar_state", "state": "INVALID_STATE"})


# 2. Initial avatar state on connection
def test_initial_avatar_state_on_connection(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        # Initial system message
        sys_msg = websocket.receive_json()
        assert sys_msg["type"] == "system"
        assert sys_msg["event"] == "connected"

        # Initial Avatar state event
        avatar_event = websocket.receive_json()
        assert avatar_event["type"] == "avatar_state"
        assert avatar_event["state"] == "IDLE"


# 3. Text interview avatar state transitions
@patch("app.api.interview_ws.process_live_candidate_message")
def test_text_interview_avatar_state_flow(mock_process_msg: AsyncMock, sync_client):
    mock_process_msg.return_value = WSAIMessageEvent(
        content="How do you handle data partitioning in microservices?",
        target_capability="System Architecture",
    )

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        websocket.receive_json()  # system connected
        websocket.receive_json()  # avatar IDLE

        websocket.send_json({
            "type": "candidate_message",
            "content": "I design distributed systems using event-driven architectures.",
        })

        # 1. Avatar transitions to THINKING
        evt_thinking = websocket.receive_json()
        assert evt_thinking["type"] == "avatar_state"
        assert evt_thinking["state"] == "THINKING"

        # 2. Avatar transitions to SPEAKING
        evt_speaking = websocket.receive_json()
        assert evt_speaking["type"] == "avatar_state"
        assert evt_speaking["state"] == "SPEAKING"

        # 3. AI Message received
        ai_msg = websocket.receive_json()
        assert ai_msg["type"] == "ai_message"
        assert "data partitioning" in ai_msg["content"]

        # 4. Avatar returns to IDLE
        evt_idle = websocket.receive_json()
        assert evt_idle["type"] == "avatar_state"
        assert evt_idle["state"] == "IDLE"


# 4. Voice interview avatar state transitions
@patch("app.api.interview_ws.get_stt_service")
@patch("app.api.interview_ws.process_live_candidate_message")
@patch("app.api.interview_ws.get_tts_service")
def test_voice_interview_avatar_state_flow(
    mock_get_tts,
    mock_process_msg: AsyncMock,
    mock_get_stt,
    sync_client,
):
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = "I use event sourcing with Kafka."
    mock_get_stt.return_value = mock_stt

    mock_process_msg.return_value = WSAIMessageEvent(
        content="How do you handle schema evolution with event sourcing?",
        target_capability="System Architecture",
    )

    mock_tts = AsyncMock()
    mock_tts.synthesize.return_value = b"AVATAR_AUDIO_SAMPLE"
    mock_get_tts.return_value = mock_tts

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        websocket.receive_json()  # system connected
        websocket.receive_json()  # avatar IDLE

        websocket.send_json({
            "type": "candidate_audio",
            "audio": base64.b64encode(b"candidate_voice_sample").decode("utf-8"),
            "content_type": "audio/webm",
        })

        # 1. Avatar transitions to LISTENING
        evt_listening = websocket.receive_json()
        assert evt_listening["type"] == "avatar_state"
        assert evt_listening["state"] == "LISTENING"

        # 2. Transcript emitted
        transcript = websocket.receive_json()
        assert transcript["type"] == "transcript"
        assert "event sourcing" in transcript["content"]

        # 3. Avatar transitions to THINKING
        evt_thinking = websocket.receive_json()
        assert evt_thinking["type"] == "avatar_state"
        assert evt_thinking["state"] == "THINKING"

        # 4. Avatar transitions to SPEAKING
        evt_speaking = websocket.receive_json()
        assert evt_speaking["type"] == "avatar_state"
        assert evt_speaking["state"] == "SPEAKING"

        # 5. AI Message emitted
        ai_msg = websocket.receive_json()
        assert ai_msg["type"] == "ai_message"
        assert "schema evolution" in ai_msg["content"]

        # 6. AI Audio emitted
        ai_audio = websocket.receive_json()
        assert ai_audio["type"] == "ai_audio"
        assert base64.b64decode(ai_audio["audio"]) == b"AVATAR_AUDIO_SAMPLE"

        # 7. Avatar returns to IDLE
        evt_idle = websocket.receive_json()
        assert evt_idle["type"] == "avatar_state"
        assert evt_idle["state"] == "IDLE"


# 5. STT failure emits ERROR avatar state and recovers to IDLE
@patch("app.api.interview_ws.get_stt_service")
def test_stt_failure_emits_error_avatar_state(mock_get_stt, sync_client):
    mock_stt = AsyncMock()
    mock_stt.transcribe.side_effect = SpeechToTextError("Whisper API error")
    mock_get_stt.return_value = mock_stt

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        websocket.receive_json()  # system connected
        websocket.receive_json()  # avatar IDLE

        websocket.send_json({
            "type": "candidate_audio",
            "audio": base64.b64encode(b"corrupt_audio").decode("utf-8"),
            "content_type": "audio/webm",
        })

        # 1. LISTENING
        evt_listening = websocket.receive_json()
        assert evt_listening["type"] == "avatar_state"
        assert evt_listening["state"] == "LISTENING"

        # 2. ERROR state
        evt_error = websocket.receive_json()
        assert evt_error["type"] == "avatar_state"
        assert evt_error["state"] == "ERROR"

        # 3. System error
        sys_err = websocket.receive_json()
        assert sys_err["type"] == "system"
        assert sys_err["event"] == "error"

        # 4. Recover to IDLE
        evt_idle = websocket.receive_json()
        assert evt_idle["type"] == "avatar_state"
        assert evt_idle["state"] == "IDLE"


# 6. TTS failure recovers to IDLE state while preserving AI message
@patch("app.api.interview_ws.get_stt_service")
@patch("app.api.interview_ws.process_live_candidate_message")
@patch("app.api.interview_ws.get_tts_service")
def test_tts_failure_recovers_to_idle_state(
    mock_get_tts,
    mock_process_msg: AsyncMock,
    mock_get_stt,
    sync_client,
):
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = "Candidate speech."
    mock_get_stt.return_value = mock_stt

    mock_process_msg.return_value = WSAIMessageEvent(
        content="Resilient AI message.",
        target_capability="System Architecture",
    )

    mock_tts = AsyncMock()
    mock_tts.synthesize.side_effect = TextToSpeechError("TTS API unavailable")
    mock_get_tts.return_value = mock_tts

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        websocket.receive_json()  # system connected
        websocket.receive_json()  # avatar IDLE

        websocket.send_json({
            "type": "candidate_audio",
            "audio": base64.b64encode(b"audio_bytes").decode("utf-8"),
            "content_type": "audio/webm",
        })

        assert websocket.receive_json()["state"] == "LISTENING"
        assert websocket.receive_json()["type"] == "transcript"
        assert websocket.receive_json()["state"] == "THINKING"
        assert websocket.receive_json()["state"] == "SPEAKING"

        ai_msg = websocket.receive_json()
        assert ai_msg["type"] == "ai_message"
        assert ai_msg["content"] == "Resilient AI message."

        tts_unavail = websocket.receive_json()
        assert tts_unavail["type"] == "system"
        assert tts_unavail["event"] == "tts_unavailable"

        evt_idle = websocket.receive_json()
        assert evt_idle["type"] == "avatar_state"
        assert evt_idle["state"] == "IDLE"


# 7. Avatar metadata endpoint (authorized)
def test_avatar_metadata_endpoint_authorized(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)

    res = sync_client.get(
        f"/api/v1/interviews/{session_id}/avatar",
        headers=auth["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["avatar_id"] == "default-interviewer"
    assert data["display_name"] == "AI Interviewer"
    assert data["voice_enabled"] is True
    assert data["avatar_enabled"] is True


# 8. Avatar metadata endpoint (cross-tenant rejected)
def test_avatar_metadata_endpoint_cross_tenant_rejected(sync_client):
    auth1, app_id, session_id, _ = setup_session_sync(sync_client)
    auth2 = create_sync_registered_client(sync_client)

    res = sync_client.get(
        f"/api/v1/interviews/{session_id}/avatar",
        headers=auth2["headers"],
    )
    assert res.status_code == 404
