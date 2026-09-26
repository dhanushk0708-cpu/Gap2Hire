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
from app.models.interview import InterviewSession
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.job import Job
from app.models.user import User
from app.schemas.interview_integrity import (
    IntegrityEventType,
    InterviewIntegrityEventCreate,
    sanitize_integrity_metadata,
)
from app.services.interview_integrity import (
    IntegritySessionAccessDeniedError,
    IntegritySessionNotFoundError,
    InvalidIntegrityEventTypeError,
    get_session_integrity_timeline,
    record_integrity_event,
)
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


def build_mock_phase8_session_and_users():
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
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

    candidate = Candidate(
        id=cand_id,
        full_name="Phase8 Verified Candidate",
        email=cand_email,
    )
    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Staff Security Engineer",
        description="Integrity, Observability, Telemetry",
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
        integrity_events=[],
    )

    candidate_user = User(
        id=cand_user_id,
        organization_id=org_id,
        email=cand_email,
        full_name="Phase8 Verified Candidate",
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
    cross_tenant_user = User(
        id=uuid.uuid4(),
        organization_id=other_org_id,
        email=f"foreign.{uuid.uuid4().hex[:6]}@example.com",
        full_name="Foreign Tenant User",
        role=UserRole.RECRUITER.value,
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

    cand_token = create_access_token(str(cand_user_id))
    other_token = create_access_token(str(other_user_id))
    manager_token = create_access_token(str(manager_user_id))

    return {
        "org_id": org_id,
        "session_id": session_id,
        "interview_session": interview_session,
        "cand_user": candidate_user,
        "other_user": other_candidate_user,
        "cross_tenant_user": cross_tenant_user,
        "manager_user": manager_user,
        "cand_token": cand_token,
        "other_token": other_token,
        "manager_token": manager_token,
    }


# --------------------------------------------------------------------------
# Test 1: Integrity event creation and metadata sanitization validation
# --------------------------------------------------------------------------
def test_integrity_event_creation_and_validation():
    event = InterviewIntegrityEventCreate(
        event_type=IntegrityEventType.TAB_HIDDEN,
        metadata={"tab_index": 1, "custom_note": "Unfocused window"},
    )
    assert event.event_type == IntegrityEventType.TAB_HIDDEN
    assert event.metadata["tab_index"] == 1
    assert event.metadata["custom_note"] == "Unfocused window"

    # Test bounded sanitization
    oversized = {f"k_{i}": f"v_{i}" for i in range(50)}
    with pytest.raises(ValueError, match="maximum allowed fields"):
        sanitize_integrity_metadata(oversized)


# --------------------------------------------------------------------------
# Test 2: Candidate can record integrity event for own session
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_candidate_can_record_event_for_own_session():
    data = build_mock_phase8_session_and_users()
    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]

    recorded = await record_integrity_event(
        session=mock_db,
        session_id=data["session_id"],
        event_type=IntegrityEventType.TAB_HIDDEN,
        user=data["cand_user"],
        metadata={"reason": "tab_hidden"},
    )

    assert recorded.event_type == "TAB_HIDDEN"
    assert recorded.interview_session_id == data["session_id"]
    assert recorded.metadata_json["reason"] == "tab_hidden"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


# --------------------------------------------------------------------------
# Test 3: Candidate cannot record event for another candidate (Forbidden)
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_candidate_cannot_record_event_for_another_candidate():
    data = build_mock_phase8_session_and_users()
    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]

    with pytest.raises(IntegritySessionAccessDeniedError, match="not authorized"):
        await record_integrity_event(
            session=mock_db,
            session_id=data["session_id"],
            event_type=IntegrityEventType.FULLSCREEN_EXIT,
            user=data["other_user"],
        )


# --------------------------------------------------------------------------
# Test 4: Cross-tenant isolation rejects session access (Not Found)
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cross_tenant_isolation_rejected():
    data = build_mock_phase8_session_and_users()
    mock_db = AsyncMock()
    # Cross tenant lookup returns None
    mock_db.scalar.return_value = None

    with pytest.raises(IntegritySessionNotFoundError, match="not found"):
        await record_integrity_event(
            session=mock_db,
            session_id=data["session_id"],
            event_type=IntegrityEventType.CAMERA_DISCONNECTED,
            user=data["cross_tenant_user"],
        )


# --------------------------------------------------------------------------
# Test 5: Invalid event type is rejected with validation error
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invalid_event_type_rejected():
    data = build_mock_phase8_session_and_users()
    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]

    with pytest.raises(InvalidIntegrityEventTypeError, match="Invalid integrity event type"):
        await record_integrity_event(
            session=mock_db,
            session_id=data["session_id"],
            event_type="UNAUTHORIZED_ACCUSATION_SIGNAL",
            user=data["cand_user"],
        )


# --------------------------------------------------------------------------
# Test 6: WebSocket integrity event is persisted and acknowledged
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
def test_websocket_integrity_event_persisted_and_acknowledged(
    mock_db_factory,
    mock_auth_ws,
    sync_client,
):
    data = build_mock_phase8_session_and_users()
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

        # Candidate sends TAB_HIDDEN integrity event
        ws.send_json({
            "type": "integrity_event",
            "event_type": "TAB_HIDDEN",
            "metadata": {"state": "hidden"},
        })

        # Receive acknowledgement
        ack = ws.receive_json()
        assert ack["type"] == "integrity_event_recorded"
        assert ack["event_type"] == "TAB_HIDDEN"
        assert "event_id" in ack
        assert "occurred_at" in ack


# --------------------------------------------------------------------------
# Test 7: WebSocket malformed integrity payload is handled safely
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
def test_websocket_malformed_integrity_payload_handled_safely(
    mock_db_factory,
    mock_auth_ws,
    sync_client,
):
    data = build_mock_phase8_session_and_users()
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

        # Send unknown event type
        ws.send_json({
            "type": "integrity_event",
            "event_type": "UNKNOWN_SIGNAL_TYPE",
        })

        err_evt = ws.receive_json()
        assert err_evt["type"] == "system"
        assert err_evt["event"] == "error"
        assert "malformed" in err_evt["content"].lower() or "invalid" in err_evt["content"].lower()

        # Connection remains alive and usable
        ws.send_json({
            "type": "integrity_event",
            "event_type": "FULLSCREEN_ENTER",
        })
        ack = ws.receive_json()
        assert ack["type"] == "integrity_event_recorded"
        assert ack["event_type"] == "FULLSCREEN_ENTER"


# --------------------------------------------------------------------------
# Test 8: Multiple valid observable signals handled sequentially
# --------------------------------------------------------------------------
@patch("app.api.interview_ws.authenticate_ws_user")
@patch("app.api.interview_ws.async_session_factory")
def test_websocket_multiple_integrity_signals_handled(
    mock_db_factory,
    mock_auth_ws,
    sync_client,
):
    data = build_mock_phase8_session_and_users()
    session_id = data["session_id"]

    mock_auth_ws.return_value = data["cand_user"]
    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    signals_to_test = [
        "CAMERA_CONNECTED",
        "MICROPHONE_CONNECTED",
        "FULLSCREEN_ENTER",
        "FULLSCREEN_EXIT",
        "TAB_VISIBLE",
    ]

    with sync_client.websocket_connect(
        f"/api/v1/interviews/{session_id}/ws?token={data['cand_token']}"
    ) as ws:
        ws.receive_json()  # system connected
        ws.receive_json()  # avatar IDLE

        for signal in signals_to_test:
            ws.send_json({
                "type": "integrity_event",
                "event_type": signal,
            })
            ack = ws.receive_json()
            assert ack["type"] == "integrity_event_recorded"
            assert ack["event_type"] == signal


# --------------------------------------------------------------------------
# Test 9: Integrity timeline endpoint returns ordered history for candidate
# --------------------------------------------------------------------------
def test_integrity_timeline_endpoint_ordered(sync_client):
    data = build_mock_phase8_session_and_users()
    session_id = data["session_id"]

    t1 = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 26, 10, 5, 0, tzinfo=timezone.utc)

    e1 = InterviewIntegrityEvent(
        id=uuid.uuid4(),
        interview_session_id=session_id,
        event_type="TAB_HIDDEN",
        occurred_at=t1,
        metadata_json={"state": "hidden"},
        created_at=t1,
    )
    e2 = InterviewIntegrityEvent(
        id=uuid.uuid4(),
        interview_session_id=session_id,
        event_type="TAB_VISIBLE",
        occurred_at=t2,
        metadata_json={"state": "visible"},
        created_at=t2,
    )

    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [e1, e2]
    mock_db.scalars.return_value = mock_scalars

    async def mock_get_db():
        yield mock_db

    from app.api.dependencies import get_current_user
    from app.db.session import get_db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: data["cand_user"]

    try:
        resp = sync_client.get(
            f"/api/v1/interviews/{session_id}/integrity-events",
            headers={"Authorization": f"Bearer {data['cand_token']}"},
        )
        assert resp.status_code == 200
        timeline = resp.json()
        assert timeline["session_id"] == str(session_id)
        assert timeline["total_events"] == 2
        assert timeline["events"][0]["event_type"] == "TAB_HIDDEN"
        assert timeline["events"][1]["event_type"] == "TAB_VISIBLE"
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------
# Test 10: HR / Hiring Manager authorized access to timeline
# --------------------------------------------------------------------------
def test_hr_manager_authorized_access_to_timeline(sync_client):
    data = build_mock_phase8_session_and_users()
    session_id = data["session_id"]

    e1 = InterviewIntegrityEvent(
        id=uuid.uuid4(),
        interview_session_id=session_id,
        event_type="FULLSCREEN_ENTER",
        occurred_at=datetime.now(timezone.utc),
        metadata_json={},
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_db.scalar.return_value = data["interview_session"]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [e1]
    mock_db.scalars.return_value = mock_scalars

    async def mock_get_db():
        yield mock_db

    from app.api.dependencies import get_current_user
    from app.db.session import get_db_session

    app.dependency_overrides[get_db_session] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: data["manager_user"]

    try:
        resp = sync_client.get(
            f"/api/v1/interviews/{session_id}/integrity-events",
            headers={"Authorization": f"Bearer {data['manager_token']}"},
        )
        assert resp.status_code == 200
        timeline = resp.json()
        assert timeline["session_id"] == str(session_id)
        assert timeline["total_events"] == 1
        assert timeline["events"][0]["event_type"] == "FULLSCREEN_ENTER"
    finally:
        app.dependency_overrides.clear()
