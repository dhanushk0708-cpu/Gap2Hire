import base64
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
        caps = [{"name": "FastAPI", "description": "Web framework"}]
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
        json={"full_name": "Voice Candidate", "email": f"cand.{uuid.uuid4()}@example.com"},
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


def receive_next_non_avatar(ws):
    while True:
        data = ws.receive_json()
        if data.get("type") != "avatar_state":
            return data


# 1. Voice connection works
def test_voice_connection_works(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)

    start_res = sync_client.patch(
        f"/api/v1/interviews/{session_id}/start",
        headers=auth["headers"],
    )
    assert start_res.status_code == 200

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        data = receive_next_non_avatar(websocket)
        assert data["type"] == "system"
        assert data["event"] == "connected"


# 2 & 3. Candidate audio accepted & STT called
@patch("app.api.interview_ws.get_stt_service")
@patch("app.api.interview_ws.process_live_candidate_message")
@patch("app.api.interview_ws.get_tts_service")
def test_candidate_audio_accepted_and_stt_called(
    mock_get_tts,
    mock_process_message: AsyncMock,
    mock_get_stt,
    sync_client,
):
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = "I have built REST APIs with FastAPI."
    mock_get_stt.return_value = mock_stt

    mock_process_message.return_value = WSAIMessageEvent(
        content="How do you handle dependency injection in FastAPI?",
        target_capability="FastAPI",
    )

    mock_tts = AsyncMock()
    mock_tts.synthesize.return_value = b"FAKE_MP3_AUDIO_BYTES"
    mock_get_tts.return_value = mock_tts

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    fake_raw_audio = b"RIFF....WAVEfmt ...."
    b64_audio = base64.b64encode(fake_raw_audio).decode("utf-8")

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connection message

        websocket.send_json({
            "type": "candidate_audio",
            "audio": b64_audio,
            "content_type": "audio/webm",
        })

        # Expect transcript event
        t_event = receive_next_non_avatar(websocket)
        assert t_event["type"] == "transcript"
        assert t_event["role"] == "candidate"
        assert t_event["content"] == "I have built REST APIs with FastAPI."

        # Expect AI text response
        ai_msg = receive_next_non_avatar(websocket)
        assert ai_msg["type"] == "ai_message"
        assert "dependency injection" in ai_msg["content"]
        assert ai_msg["target_capability"] == "FastAPI"

        # Expect AI audio response
        ai_audio = receive_next_non_avatar(websocket)
        assert ai_audio["type"] == "ai_audio"
        assert ai_audio["content_type"] == "audio/mpeg"
        decoded_audio = base64.b64decode(ai_audio["audio"])
        assert decoded_audio == b"FAKE_MP3_AUDIO_BYTES"

    mock_stt.transcribe.assert_called_once_with(
        audio_bytes=fake_raw_audio,
        content_type="audio/webm",
    )


# 4 & 5 & 6. Transcript and AI response persisted in DB via existing interview engine
@patch("app.api.interview_ws.get_stt_service")
@patch("app.services.interview.generate_live_ai_response")
@patch("app.api.interview_ws.get_tts_service")
def test_transcript_and_ai_response_persisted(
    mock_get_tts,
    mock_ai_gen: AsyncMock,
    mock_get_stt,
    sync_client,
):
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = "I use asyncpg and SQLAlchemy for database pooling."
    mock_get_stt.return_value = mock_stt

    mock_ai_gen.return_value = WSAIMessageEvent(
        content="How do you handle schema migrations across environments?",
        target_capability="FastAPI",
    )

    mock_tts = AsyncMock()
    mock_tts.synthesize.return_value = b"MOCK_TTS_AUDIO"
    mock_get_tts.return_value = mock_tts

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    fake_audio = b"AUDIO_SAMPLE_DATA"
    b64_audio = base64.b64encode(fake_audio).decode("utf-8")

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connected confirmation

        websocket.send_json({
            "type": "candidate_audio",
            "audio": b64_audio,
            "content_type": "audio/wav",
        })

        # Consume transcript, ai_message, and ai_audio
        receive_next_non_avatar(websocket)  # transcript
        receive_next_non_avatar(websocket)  # ai_message
        receive_next_non_avatar(websocket)  # ai_audio

    # Verify session detail in DB via REST endpoint
    session_res = sync_client.get(
        f"/api/v1/interviews/{session_id}",
        headers=auth["headers"],
    )
    assert session_res.status_code == 200
    detail = session_res.json()
    messages = detail["messages"]
    roles = [m["role"] for m in messages]

    assert "CANDIDATE" in roles
    assert "AI" in roles

    cand_msgs = [m for m in messages if m["role"] == "CANDIDATE"]
    assert any("SQLAlchemy" in m["content"] for m in cand_msgs)

    ai_msgs = [m for m in messages if m["role"] == "AI"]
    assert any("schema migrations" in m["content"] for m in ai_msgs)


# 7. TTS called with AI text and ai_audio returned
@patch("app.api.interview_ws.get_stt_service")
@patch("app.api.interview_ws.process_live_candidate_message")
@patch("app.api.interview_ws.get_tts_service")
def test_tts_called_and_ai_audio_emitted(
    mock_get_tts,
    mock_process_msg: AsyncMock,
    mock_get_stt,
    sync_client,
):
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = "Candidate speech transcript."
    mock_get_stt.return_value = mock_stt

    mock_process_msg.return_value = WSAIMessageEvent(
        content="AI generated follow-up question text.",
        target_capability="FastAPI",
    )

    mock_tts = AsyncMock()
    mock_tts.synthesize.return_value = b"SYNTHESIZED_MP3_STREAM"
    mock_get_tts.return_value = mock_tts

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connected

        websocket.send_json({
            "type": "candidate_audio",
            "audio": base64.b64encode(b"candidate_voice").decode("utf-8"),
            "content_type": "audio/webm",
        })

        t_ev = receive_next_non_avatar(websocket)  # transcript
        assert t_ev["type"] == "transcript"
        msg_ev = receive_next_non_avatar(websocket)  # ai_message
        assert msg_ev["type"] == "ai_message"
        ai_audio_event = receive_next_non_avatar(websocket)

        assert ai_audio_event["type"] == "ai_audio"
        assert base64.b64decode(ai_audio_event["audio"]) == b"SYNTHESIZED_MP3_STREAM"

    mock_tts.synthesize.assert_called_once_with("AI generated follow-up question text.")


# 8. STT failure gracefully handled
@patch("app.api.interview_ws.get_stt_service")
@patch("app.api.interview_ws.process_live_candidate_message")
def test_stt_failure_gracefully_handled(
    mock_process_msg: AsyncMock,
    mock_get_stt,
    sync_client,
):
    mock_stt = AsyncMock()
    mock_stt.transcribe.side_effect = SpeechToTextError("Whisper API connection error")
    mock_get_stt.return_value = mock_stt

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connected

        websocket.send_json({
            "type": "candidate_audio",
            "audio": base64.b64encode(b"corrupted_audio").decode("utf-8"),
            "content_type": "audio/webm",
        })

        err_event = receive_next_non_avatar(websocket)
        assert err_event["type"] == "system"
        assert err_event["event"] == "error"
        assert "Speech transcription failed" in err_event["content"]

    # Verify interview engine was NOT invoked
    mock_process_msg.assert_not_called()


# 9. TTS failure does not destroy AI text response
@patch("app.api.interview_ws.get_stt_service")
@patch("app.api.interview_ws.process_live_candidate_message")
@patch("app.api.interview_ws.get_tts_service")
def test_tts_failure_does_not_destroy_ai_text(
    mock_get_tts,
    mock_process_msg: AsyncMock,
    mock_get_stt,
    sync_client,
):
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = "Candidate speech content."
    mock_get_stt.return_value = mock_stt

    mock_process_msg.return_value = WSAIMessageEvent(
        content="Important AI technical question that must not be lost.",
        target_capability="FastAPI",
    )

    mock_tts = AsyncMock()
    mock_tts.synthesize.side_effect = TextToSpeechError("TTS provider timeout")
    mock_get_tts.return_value = mock_tts

    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connected

        websocket.send_json({
            "type": "candidate_audio",
            "audio": base64.b64encode(b"voice_bytes").decode("utf-8"),
            "content_type": "audio/webm",
        })

        t_msg = receive_next_non_avatar(websocket)  # transcript
        assert t_msg["type"] == "transcript"

        ai_msg = receive_next_non_avatar(websocket)
        assert ai_msg["type"] == "ai_message"
        assert "Important AI technical question" in ai_msg["content"]

        tts_unavail = receive_next_non_avatar(websocket)
        assert tts_unavail["type"] == "system"
        assert tts_unavail["event"] == "tts_unavailable"
        assert "temporarily unavailable" in tts_unavail["content"]


# 10. Security: audio size exceeded, invalid base64, candidate role rejected
def test_security_validations(sync_client):
    auth, app_id, session_id, _ = setup_session_sync(sync_client)
    cand_token = create_candidate_token_sync(sync_client)

    sync_client.patch(f"/api/v1/interviews/{session_id}/start", headers=auth["headers"])

    # A. Candidate role is rejected from connecting
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with sync_client.websocket_connect(
            f"/api/v1/interviews/{session_id}/ws?token={cand_token}"
        ):
            pass
    assert exc_info.value.code == 1008

    # B. Connected HR sending invalid base64
    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={auth['token']}"
    ) as websocket:
        receive_next_non_avatar(websocket)  # connected

        websocket.send_json({
            "type": "candidate_audio",
            "audio": "!!!NOT_VALID_BASE64!!!",
            "content_type": "audio/webm",
        })

        err_event = receive_next_non_avatar(websocket)
        assert err_event["type"] == "system"
        assert err_event["event"] == "error"
        assert "base64" in err_event["content"].lower()

        # C. Oversized audio (>5MB)
        huge_audio = b"A" * (6 * 1024 * 1024)
        b64_huge = base64.b64encode(huge_audio).decode("utf-8")

        websocket.send_json({
            "type": "candidate_audio",
            "audio": b64_huge,
            "content_type": "audio/webm",
        })

        err_huge = receive_next_non_avatar(websocket)
        assert err_huge["type"] == "system"
        assert err_huge["event"] == "error"
        assert "exceeds limit" in err_huge["content"]
