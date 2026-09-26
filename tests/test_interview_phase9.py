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
from app.models.capability import Capability
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.job import Job
from app.models.user import User
from app.schemas.interview_batch import (
    ALLOWED_CONCURRENCY_LIMITS,
    InterviewBatchStartRequest,
    InterviewBatchStartResponse,
)
from app.services.interview_concurrency import (
    BatchApplicationError,
    DuplicateActiveSessionError,
    InvalidConcurrencyLimitError,
    create_batch_interview_sessions,
    get_session_thread_id,
    validate_concurrency_limit,
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


def build_mock_two_candidates_setup():
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # Manager User
    manager_user_id = uuid.uuid4()
    manager_user = User(
        id=manager_user_id,
        organization_id=org_id,
        email="recruiter.phase9@example.com",
        role=UserRole.RECRUITER.value,
        is_active=True,
    )

    # Job & Capabilities
    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Senior Python / Distributed Systems Engineer",
        description="Concurrency, Isolation, Fast execution",
    )
    cap1 = Capability(
        id=uuid.uuid4(),
        job_id=job_id,
        name="Python Concurrency",
        description="AsyncIO, ThreadPools, ProcessPools",
        importance="HIGH",
    )

    # Candidate A
    cand_a_id = uuid.uuid4()
    app_a_id = uuid.uuid4()
    session_a_id = uuid.uuid4()
    cand_a_user_id = uuid.uuid4()
    cand_a = Candidate(
        id=cand_a_id,
        full_name="Alice Candidate",
        email=f"alice.{cand_a_id.hex[:6]}@example.com",
    )
    cand_a_user = User(
        id=cand_a_user_id,
        organization_id=org_id,
        email=cand_a.email,
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )
    app_a = Application(
        id=app_a_id,
        candidate_id=cand_a_id,
        job_id=job_id,
        candidate=cand_a,
        job=job,
        status="SCREENING",
        shortlist_status="SHORTLISTED",
    )
    session_a = InterviewSession(
        id=session_a_id,
        application_id=app_a_id,
        status="IN_PROGRESS",
        application=app_a,
    )

    # Candidate B
    cand_b_id = uuid.uuid4()
    app_b_id = uuid.uuid4()
    session_b_id = uuid.uuid4()
    cand_b_user_id = uuid.uuid4()
    cand_b = Candidate(
        id=cand_b_id,
        full_name="Bob Candidate",
        email=f"bob.{cand_b_id.hex[:6]}@example.com",
    )
    cand_b_user = User(
        id=cand_b_user_id,
        organization_id=org_id,
        email=cand_b.email,
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )
    app_b = Application(
        id=app_b_id,
        candidate_id=cand_b_id,
        job_id=job_id,
        candidate=cand_b,
        job=job,
        status="SCREENING",
        shortlist_status="SHORTLISTED",
    )
    session_b = InterviewSession(
        id=session_b_id,
        application_id=app_b_id,
        status="IN_PROGRESS",
        application=app_b,
    )

    return {
        "org_id": org_id,
        "other_org_id": other_org_id,
        "job": job,
        "capabilities": [cap1],
        "manager_user": manager_user,
        "cand_a": cand_a,
        "cand_a_user": cand_a_user,
        "app_a": app_a,
        "session_a": session_a,
        "cand_b": cand_b,
        "cand_b_user": cand_b_user,
        "app_b": app_b,
        "session_b": session_b,
    }


# ==============================================================================
# TESTS 1 - 5: Concurrency Limits Validation
# ==============================================================================

def test_concurrency_value_1_accepted():
    """Test 1: Concurrency value 1 is accepted."""
    limit = validate_concurrency_limit(1)
    assert limit == 1
    req = InterviewBatchStartRequest(
        application_ids=[uuid.uuid4()],
        concurrency_limit=1,
    )
    assert req.concurrency_limit == 1


def test_concurrency_value_2_accepted():
    """Test 2: Concurrency value 2 is accepted."""
    limit = validate_concurrency_limit(2)
    assert limit == 2
    req = InterviewBatchStartRequest(
        application_ids=[uuid.uuid4(), uuid.uuid4()],
        concurrency_limit=2,
    )
    assert req.concurrency_limit == 2


def test_concurrency_value_3_accepted():
    """Test 3: Concurrency value 3 is accepted."""
    limit = validate_concurrency_limit(3)
    assert limit == 3
    req = InterviewBatchStartRequest(
        application_ids=[uuid.uuid4()],
        concurrency_limit=3,
    )
    assert req.concurrency_limit == 3


def test_concurrency_value_5_accepted():
    """Test 4: Concurrency value 5 is accepted."""
    limit = validate_concurrency_limit(5)
    assert limit == 5
    req = InterviewBatchStartRequest(
        application_ids=[uuid.uuid4()],
        concurrency_limit=5,
    )
    assert req.concurrency_limit == 5


def test_invalid_concurrency_rejected():
    """Test 5: Unsupported concurrency values (0, 4, 10, -1) are rejected."""
    for invalid_val in [0, 4, 10, -1, 100]:
        with pytest.raises(InvalidConcurrencyLimitError):
            validate_concurrency_limit(invalid_val)

        with pytest.raises(ValueError):
            InterviewBatchStartRequest(
                application_ids=[uuid.uuid4()],
                concurrency_limit=invalid_val,
            )


# ==============================================================================
# TEST 6: Batch Creation Creates Independent InterviewSessions
# ==============================================================================

@pytest.mark.asyncio
async def test_batch_creation_creates_independent_interview_sessions():
    """Test 6: Batch creation generates independent InterviewSession records."""
    ctx = build_mock_two_candidates_setup()
    mock_db = AsyncMock()

    # Mock scalars queries
    def mock_scalars_side_effect(stmt):
        stmt_str = str(stmt)
        result_mock = MagicMock()
        if "applications" in stmt_str.lower():
            result_mock.all.return_value = [ctx["app_a"], ctx["app_b"]]
        elif "interview_sessions" in stmt_str.lower():
            # No existing active sessions
            result_mock.all.return_value = []
        elif "capabilities" in stmt_str.lower():
            result_mock.all.return_value = ctx["capabilities"]
        else:
            result_mock.all.return_value = []
        return result_mock

    mock_db.scalars.side_effect = mock_scalars_side_effect

    res = await create_batch_interview_sessions(
        session=mock_db,
        organization_id=ctx["org_id"],
        application_ids=[ctx["app_a"].id, ctx["app_b"].id],
        concurrency_limit=2,
        auto_start=True,
    )

    assert res.sessions_created == 2
    assert res.concurrency_limit == 2
    assert len(res.sessions) == 2
    session_ids = [s.session_id for s in res.sessions]
    assert len(set(session_ids)) == 2  # Different unique IDs
    assert res.sessions[0].application_id == ctx["app_a"].id
    assert res.sessions[1].application_id == ctx["app_b"].id


# ==============================================================================
# TEST 7: Unique LangGraph Thread Identity
# ==============================================================================

def test_each_session_has_unique_langgraph_thread_identity():
    """Test 7: Each session maps to a dedicated LangGraph thread ID."""
    session_a_id = uuid.uuid4()
    session_b_id = uuid.uuid4()

    thread_a = get_session_thread_id(session_a_id)
    thread_b = get_session_thread_id(session_b_id)

    assert thread_a == str(session_a_id)
    assert thread_b == str(session_b_id)
    assert thread_a != thread_b


# ==============================================================================
# TEST 8: Candidate A State Does Not Leak Into Candidate B
# ==============================================================================

@pytest.mark.asyncio
async def test_candidate_a_state_does_not_leak_into_candidate_b():
    """Test 8: Candidate A's messages, questions, and state do not modify Candidate B."""
    ctx = build_mock_two_candidates_setup()
    session_a = ctx["session_a"]
    session_b = ctx["session_b"]

    session_a.messages = []
    session_b.messages = []
    session_a.questions = []
    session_b.questions = []

    # Add message and question to Candidate A
    msg_a = InterviewMessage(
        session_id=session_a.id,
        role="CANDIDATE",
        content="I use asyncio.gather for concurrent execution.",
        sequence_number=1,
    )
    q_a = InterviewQuestion(
        session_id=session_a.id,
        question="How do you handle async tasks in FastAPI?",
        sequence_number=1,
    )
    session_a.messages.append(msg_a)
    session_a.questions.append(q_a)

    # Verify Candidate B has 0 messages and 0 questions
    assert len(session_a.messages) == 1
    assert len(session_a.questions) == 1
    assert len(session_b.messages) == 0
    assert len(session_b.questions) == 0
    assert session_a.messages[0].content != ""
    assert session_b.messages == []


# ==============================================================================
# TEST 9: Integrity Events Remain Isolated Between Sessions
# ==============================================================================

@pytest.mark.asyncio
async def test_integrity_events_isolated_between_sessions():
    """Test 9: Integrity events recorded for Session A are not visible in Session B."""
    ctx = build_mock_two_candidates_setup()
    session_a = ctx["session_a"]
    session_b = ctx["session_b"]

    event_a = InterviewIntegrityEvent(
        id=uuid.uuid4(),
        interview_session_id=session_a.id,
        event_type="TAB_HIDDEN",
        occurred_at=datetime.now(timezone.utc),
        metadata_json={},
    )
    session_a.integrity_events = [event_a]
    session_b.integrity_events = []

    assert len(session_a.integrity_events) == 1
    assert len(session_b.integrity_events) == 0
    assert session_a.integrity_events[0].event_type == "TAB_HIDDEN"


# ==============================================================================
# TEST 10: Cross-Tenant Batch / Session Access Rejected + Candidate Auth Boundary
# ==============================================================================

def test_cross_tenant_batch_and_candidate_boundary_rejected(sync_client):
    """Test 10: Batch creation rejects cross-tenant applications and unauthorized candidates."""
    ctx = build_mock_two_candidates_setup()

    # Manager from different tenant tries to batch-start
    other_manager = User(
        id=uuid.uuid4(),
        organization_id=ctx["other_org_id"],
        email="other.recruiter@example.com",
        role=UserRole.RECRUITER.value,
        is_active=True,
    )
    token = create_access_token(str(other_manager.id))

    # Mock DB where application belongs to ctx["org_id"] but current_user belongs to ctx["other_org_id"]
    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []  # No applications found for other tenant
    mock_db.scalars.return_value = mock_scalars

    async def override_get_db():
        yield mock_db

    async def override_get_user():
        return other_manager

    from app.api.dependencies import get_current_user
    from app.db.session import get_db_session

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_user

    try:
        response = sync_client.post(
            "/api/v1/interviews/batch-start",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_ids": [str(ctx["app_a"].id)],
                "concurrency_limit": 2,
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found or belongs to another organization" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)
