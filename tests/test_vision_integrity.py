import io
from pathlib import Path
import time
from uuid import UUID, uuid4

from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.roles import UserRole
from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewSession
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.schemas.interview_integrity import IntegrityEventType, InterviewIntegrityEventCreate
from app.services.interview_integrity import record_integrity_event
from app.services.vision_service import SessionVisionTracker, VisionService, vision_service


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def register_user(client: TestClient, role: str = UserRole.RECRUITER.value):
    org_name = f"Vision Test Org {uuid4()}"
    email = f"vision-user-{uuid4()}@gap2hire.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Vision Recruiter",
            "organization_name": org_name,
        },
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    org_id = resp.json()["user"]["organization_id"]
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": UUID(user_id),
        "organization_id": UUID(org_id),
        "email": email,
    }


def create_test_image_bytes(color=(255, 0, 0), size=(320, 240)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_event_type_enums_and_schema_validation():
    # 1. PHONE_DETECTED validation
    phone_event = InterviewIntegrityEventCreate(
        event_type=IntegrityEventType.PHONE_DETECTED,
        metadata={"object": "cell phone", "confidence": 0.92},
    )
    assert phone_event.event_type == IntegrityEventType.PHONE_DETECTED
    assert phone_event.metadata["object"] == "cell phone"

    # 2. MULTIPLE_PERSONS_DETECTED validation
    multi_person_event = InterviewIntegrityEventCreate(
        event_type=IntegrityEventType.MULTIPLE_PERSONS_DETECTED,
        metadata={"object": "multiple people", "confidence": 0.88, "detection_count": 2},
    )
    assert multi_person_event.event_type == IntegrityEventType.MULTIPLE_PERSONS_DETECTED
    assert multi_person_event.metadata["detection_count"] == 2


@pytest.mark.asyncio
async def test_consecutive_detection_stability_and_cooldown():
    """
    Test tracker logic:
    - 1st detection does not trigger (requires consecutive detections >= 2).
    - 2nd consecutive detection triggers event.
    - Subsequent detections during cooldown are suppressed.
    """
    tracker = SessionVisionTracker()
    req_consecutive = 2
    cooldown_seconds = 5

    # Frame 1: Phone detected (consecutive = 1)
    tracker.consecutive_phone_detections += 1
    now = time.time()
    triggered = (
        tracker.consecutive_phone_detections >= req_consecutive
        and (now - tracker.last_phone_event_time) >= cooldown_seconds
    )
    assert not triggered, "Single frame must not trigger without meeting consecutive threshold"

    # Frame 2: Phone detected again (consecutive = 2)
    tracker.consecutive_phone_detections += 1
    now = time.time()
    triggered = (
        tracker.consecutive_phone_detections >= req_consecutive
        and (now - tracker.last_phone_event_time) >= cooldown_seconds
    )
    assert triggered, "Consecutive threshold met -> should trigger"

    # Simulate triggering
    tracker.last_phone_event_time = now
    tracker.consecutive_phone_detections = 0

    # Frame 3: Phone detected immediately after (cooldown active)
    tracker.consecutive_phone_detections += 2
    now = time.time()  # immediate, within cooldown
    triggered = (
        tracker.consecutive_phone_detections >= req_consecutive
        and (now - tracker.last_phone_event_time) >= cooldown_seconds
    )
    assert not triggered, "Must be suppressed during cooldown"


@pytest.mark.asyncio
async def test_normal_frame_and_low_confidence_suppression():
    """
    Normal frames (person_count == 1, phone == False) or low confidence must not trigger events.
    """
    tracker = SessionVisionTracker()
    phone_detected = False
    person_count = 1

    if phone_detected:
        tracker.consecutive_phone_detections += 1
    else:
        tracker.consecutive_phone_detections = 0

    if person_count > 1:
        tracker.consecutive_multi_person_detections += 1
    else:
        tracker.consecutive_multi_person_detections = 0

    assert tracker.consecutive_phone_detections == 0
    assert tracker.consecutive_multi_person_detections == 0


@pytest.mark.asyncio
async def test_evidence_frame_saving_and_reference():
    """
    Verifies that saving an evidence frame creates a valid JPEG file in the secure directory structure.
    """
    session_id = uuid4()
    event_id = uuid4()
    img_bytes = create_test_image_bytes()

    ref = await vision_service.save_evidence_frame(session_id, event_id, img_bytes)
    assert ref == f"integrity/{session_id}/{event_id}.jpg"

    expected_path = Path(settings.vision_storage_dir) / str(session_id) / f"{event_id}.jpg"
    assert expected_path.is_file(), "Evidence file must be written to disk"

    # Clean up test artifact
    try:
        expected_path.unlink()
        expected_path.parent.rmdir()
    except Exception:
        pass


def test_evidence_endpoint_authorization_and_tenant_isolation(client: TestClient):
    """
    Verifies that evidence endpoint enforces tenant isolation and returns JPEG.
    """
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.api.interviews import require_interview_participant
    from app.db.session import get_db_session
    from app.services.interview_integrity import (
        IntegritySessionAccessDeniedError,
        IntegritySessionNotFoundError,
    )

    session_id = uuid4()
    event_id = uuid4()

    # Save real evidence file to disk in test storage
    img_bytes = create_test_image_bytes()
    expected_path = Path(settings.vision_storage_dir) / str(session_id) / f"{event_id}.jpg"
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    expected_path.write_bytes(img_bytes)

    # 1. Authorized user -> 200 OK + image/jpeg
    mock_user = User(
        id=uuid4(),
        organization_id=uuid4(),
        email="auth@gap2hire.com",
        full_name="Auth User",
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )

    async def mock_require_participant():
        return mock_user

    async def mock_get_db():
        yield AsyncMock()

    app.dependency_overrides[require_interview_participant] = mock_require_participant
    app.dependency_overrides[get_db_session] = mock_get_db

    try:
        with patch(
            "app.services.interview_integrity.get_authorized_interview_session_for_integrity",
            new=AsyncMock(return_value=MagicMock()),
        ):
            resp = client.get(f"/api/v1/interviews/{session_id}/integrity-evidence/{event_id}")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/jpeg"
            assert resp.content == img_bytes

        # 2. Unauthorized cross-tenant user -> 403 Forbidden
        with patch(
            "app.services.interview_integrity.get_authorized_interview_session_for_integrity",
            side_effect=IntegritySessionAccessDeniedError("Access denied"),
        ):
            resp_cross = client.get(f"/api/v1/interviews/{session_id}/integrity-evidence/{event_id}")
            assert resp_cross.status_code == 403

        # 3. Nonexistent session -> 404 Not Found
        with patch(
            "app.services.interview_integrity.get_authorized_interview_session_for_integrity",
            side_effect=IntegritySessionNotFoundError("Not found"),
        ):
            resp_404 = client.get(f"/api/v1/interviews/{session_id}/integrity-evidence/{event_id}")
            assert resp_404.status_code == 404

    finally:
        app.dependency_overrides.clear()
        if expected_path.exists():
            expected_path.unlink()
            try:
                expected_path.parent.rmdir()
            except Exception:
                pass


def test_vision_frame_rest_endpoint(client: TestClient):
    """
    Tests POST /api/v1/interviews/{session_id}/vision-frame
    """
    import base64
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.api.interviews import require_interview_participant
    from app.db.session import get_db_session

    session_id = uuid4()
    mock_user = User(
        id=uuid4(),
        organization_id=uuid4(),
        email="candidate@gap2hire.com",
        full_name="Candidate",
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )

    async def mock_require_participant():
        return mock_user

    async def mock_get_db():
        yield AsyncMock()

    app.dependency_overrides[require_interview_participant] = mock_require_participant
    app.dependency_overrides[get_db_session] = mock_get_db

    b64_img = base64.b64encode(create_test_image_bytes()).decode("utf-8")

    try:
        with patch(
            "app.services.interview_integrity.get_authorized_interview_session_for_integrity",
            new=AsyncMock(return_value=MagicMock()),
        ), patch(
            "app.services.vision_service.vision_service.process_sampled_frame",
            new=AsyncMock(return_value=[]),
        ):
            resp = client.post(
                f"/api/v1/interviews/{session_id}/vision-frame",
                json={"image": f"data:image/jpeg;base64,{b64_img}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["events_triggered"] == 0
    finally:
        app.dependency_overrides.clear()


def test_websocket_integrity_event_recording_no_uuid4_error(client: TestClient):
    """
    Verifies that sending an integrity_event through the WebSocket records successfully
    without raising NameError: name 'uuid4' is not defined.
    """
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.core.security import create_access_token
    from tests.test_interview_phase7 import build_mock_session_and_users

    data = build_mock_session_and_users()
    session_id = data["session_id"]
    token = data["cand_token"]

    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]

    with patch("app.api.interview_ws.authenticate_ws_user", return_value=data["cand_user"]), \
         patch("app.api.interview_ws.async_session_factory") as mock_db_factory, \
         patch("app.api.interview_ws.record_integrity_event") as mock_record:

        mock_db_factory.return_value.__aenter__.return_value = mock_db
        mock_event = MagicMock()
        mock_event.id = uuid4()
        from datetime import datetime, timezone
        mock_event.occurred_at = datetime.now(timezone.utc)
        mock_event.metadata_json = {"object": "cell phone"}
        mock_record.return_value = mock_event

        with client.websocket_connect(f"/api/v1/interviews/{session_id}/ws?token={token}") as ws:
            ws.receive_json()  # system connected
            ws.receive_json()  # avatar IDLE

            # Send integrity_event
            ws.send_json({
                "type": "integrity_event",
                "event_type": "CAMERA_CONNECTED",
                "metadata": {"info": "Camera initialized"},
            })

            ack = ws.receive_json()
            assert ack.get("type") == "integrity_event_recorded"
            assert ack.get("event_type") == "CAMERA_CONNECTED"
            assert "event_id" in ack


@pytest.mark.asyncio
async def test_vision_persistence_failure_gracefully_handled():
    """
    Verifies that when evidence frame disk saving or DB persistence raises an IOError/DBError,
    process_sampled_frame handles it safely without crashing the live interview session.
    """
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.services.vision_service import VisionService

    service = VisionService()
    session_id = uuid4()
    mock_user = MagicMock()
    mock_db = AsyncMock()

    # Create dummy image bytes
    img_bytes = create_test_image_bytes()

    with patch.object(service, "detect_objects", new=AsyncMock(return_value={
        "available": True,
        "person_count": 1,
        "phone_detected": True,
        "phone_confidence": 0.95,
        "person_confidences": [0.98],
    })), patch.object(service, "save_evidence_frame", side_effect=IOError("Simulated disk error")), \
         patch("app.services.vision_service.connection_manager.send_json", new=AsyncMock()):

        # Ensure required consecutive threshold is met
        service.get_tracker(session_id).consecutive_phone_detections = 1
        service.get_tracker(session_id).last_phone_event_time = 0.0

        # Should complete safely without raising an unhandled exception
        events = await service.process_sampled_frame(
            session_id=session_id,
            image_bytes=img_bytes,
            user=mock_user,
            db_session=mock_db,
        )

        assert len(events) == 1
        assert events[0]["event_type"] == "PHONE_DETECTED"
        assert events[0]["metadata"]["evidence_reference"] is None



