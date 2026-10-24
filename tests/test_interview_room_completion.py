import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.roles import UserRole
from app.core.security import create_access_token
from app.db.session import get_db_session
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.interview_plan import InterviewPlan, InterviewPlanRound, InterviewPlanQuestion
from app.models.interview_report import InterviewReportModel
from app.models.job import Job
from app.models.user import User
from app.schemas.interview_integrity import IntegrityEventType
from app.services.interview import (
    ALLOWED_INTERVIEW_DURATIONS,
    InterviewExpiredError,
    InterviewSessionNotFoundError,
    InvalidSessionStateError,
    MediaReadinessRequiredError,
    complete_interview_session_atomic,
    generate_next_question_for_session,
    get_interview_execution_state,
    start_interview_session,
    submit_interview_answer,
)
from app.services.interview_report import (
    generate_and_persist_interview_report,
    get_persisted_interview_report,
)


@pytest.fixture(scope="module")
def sync_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def mock_interview_graph_checkpointer():
    """Prevent LangGraph checkpointer from connecting to PostgreSQL during unit tests."""
    with patch("app.services.interview_graph.start_or_resume_interview_graph", new=AsyncMock()):
        yield


def build_test_context(session_status: str = "CREATED"):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    app_id = uuid.uuid4()
    session_id = uuid.uuid4()
    recruiter_id = uuid.uuid4()
    candidate_user_id = uuid.uuid4()

    recruiter = User(
        id=recruiter_id,
        organization_id=org_id,
        email="hr.lead@example.com",
        full_name="HR Lead",
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )

    candidate = Candidate(
        id=cand_id,
        full_name="Robin TestCandidate",
        email=f"robin.{cand_id.hex[:6]}@example.com",
    )

    candidate_user = User(
        id=candidate_user_id,
        organization_id=org_id,
        email=candidate.email,
        full_name="Robin TestCandidate",
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )

    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Staff Distributed Systems Architect",
        description="Raft, Paxos, High concurrency, Low latency",
    )

    cap1 = Capability(
        id=uuid.uuid4(),
        job_id=job_id,
        name="Distributed Systems",
        description="Consensus protocols and fault tolerance",
        importance="HIGH",
    )

    application = Application(
        id=app_id,
        candidate_id=cand_id,
        job_id=job_id,
        status="INTERVIEW",
        shortlist_status="SHORTLISTED",
        candidate=candidate,
        job=job,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    session = InterviewSession(
        id=session_id,
        application_id=app_id,
        status=session_status,
        application=application,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        duration_minutes=30,
        deadline_at=None,
        completion_reason=None,
        report_status="NOT_STARTED",
        questions=[],
        messages=[],
        answer_analyses=[],
        integrity_events=[],
    )

    return {
        "org_id": org_id,
        "other_org_id": other_org_id,
        "job_id": job_id,
        "cand_id": cand_id,
        "app_id": app_id,
        "session_id": session_id,
        "recruiter": recruiter,
        "candidate": candidate,
        "candidate_user": candidate_user,
        "job": job,
        "capability": cap1,
        "application": application,
        "session": session,
    }


def setup_mock_db(ctx, existing_report=None, plan=None):
    mock_db = AsyncMock()

    def mock_scalar(stmt):
        stmt_str = str(stmt).lower()
        if "coalesce" in stmt_str or "max" in stmt_str or "count" in stmt_str:
            return len(ctx["session"].messages or [])
        if "interview_sessions" in stmt_str:
            return ctx["session"]
        if "interview_reports" in stmt_str:
            return existing_report
        if "interview_plans" in stmt_str:
            return plan
        if "candidate_scorecards" in stmt_str:
            return None
        if "applications" in stmt_str:
            return ctx["application"]
        return ctx["session"]

    def mock_scalars(stmt):
        stmt_str = str(stmt).lower()
        m = MagicMock()
        if "capabilities" in stmt_str:
            m.all.return_value = [ctx["capability"]]
        elif "interview_plans" in stmt_str:
            m.all.return_value = [plan] if plan else []
        elif "interview_messages" in stmt_str:
            m.all.return_value = ctx["session"].messages or []
        elif "interview_rounds" in stmt_str:
            m.all.return_value = plan.rounds if plan else []
        else:
            m.all.return_value = []
        return m

    mock_db.scalar.side_effect = mock_scalar
    mock_db.scalars.side_effect = mock_scalars
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    return mock_db


# =========================================================================
# 1. Enforce interview duration tests (5min, 15min, deadline persistence)
# =========================================================================
@pytest.mark.asyncio
async def test_start_interview_duration_5min_and_15min():
    ctx = build_test_context(session_status="CREATED")
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        res5 = await start_interview_session(
            session=db,
            session_id=ctx["session_id"],
            organization_id=ctx["org_id"],
            duration_minutes=5,
            media_verified=True,
        )
        assert res5.duration_minutes == 5
        assert res5.deadline_at is not None
        assert res5.status == "IN_PROGRESS"
        diff = (res5.deadline_at - res5.started_at).total_seconds()
        assert 295 <= diff <= 305

    ctx2 = build_test_context(session_status="CREATED")
    db2 = setup_mock_db(ctx2)
    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx2["session"]):
        res15 = await start_interview_session(
            session=db2,
            session_id=ctx2["session_id"],
            organization_id=ctx2["org_id"],
            duration_minutes=15,
            media_verified=True,
        )
        assert res15.duration_minutes == 15
        assert res15.deadline_at is not None
        diff15 = (res15.deadline_at - res15.started_at).total_seconds()
        assert 895 <= diff15 <= 905


@pytest.mark.asyncio
async def test_invalid_duration_rejected():
    ctx = build_test_context(session_status="CREATED")
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        with pytest.raises(InvalidSessionStateError) as exc_info:
            await start_interview_session(
                session=db,
                session_id=ctx["session_id"],
                organization_id=ctx["org_id"],
                duration_minutes=7,  # invalid
                media_verified=True,
            )
        assert "Invalid interview duration 7" in str(exc_info.value)


@pytest.mark.asyncio
async def test_deadline_persisted_across_reconnect():
    ctx = build_test_context(session_status="IN_PROGRESS")
    fixed_start = datetime.now(timezone.utc) - timedelta(minutes=10)
    fixed_deadline = fixed_start + timedelta(minutes=30)
    ctx["session"].started_at = fixed_start
    ctx["session"].duration_minutes = 30
    ctx["session"].deadline_at = fixed_deadline
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        res = await start_interview_session(
            session=db,
            session_id=ctx["session_id"],
            organization_id=ctx["org_id"],
            duration_minutes=30,
            media_verified=True,
        )
        assert res.started_at == fixed_start
        assert res.deadline_at == fixed_deadline
        assert res.status == "IN_PROGRESS"


# =========================================================================
# 2. Expiration completion and rejection of late answers/questions
# =========================================================================
@pytest.mark.asyncio
async def test_automatic_atomic_completion_at_expiration():
    ctx = build_test_context(session_status="IN_PROGRESS")
    past_start = datetime.now(timezone.utc) - timedelta(minutes=35)
    past_deadline = past_start + timedelta(minutes=30)
    ctx["session"].started_at = past_start
    ctx["session"].duration_minutes = 30
    ctx["session"].deadline_at = past_deadline
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        with patch("app.services.interview.complete_interview_session_atomic") as mock_complete:
            mock_complete.return_value = ctx["session"]
            state = await get_interview_execution_state(
                session=db,
                session_id=ctx["session_id"],
                organization_id=ctx["org_id"],
            )
            mock_complete.assert_called_once()
            _, kwargs = mock_complete.call_args
            assert kwargs.get("reason") == "TIME_EXPIRED"


@pytest.mark.asyncio
async def test_late_candidate_answer_rejected_when_expired():
    ctx = build_test_context(session_status="IN_PROGRESS")
    past_start = datetime.now(timezone.utc) - timedelta(minutes=35)
    past_deadline = past_start + timedelta(minutes=30)
    ctx["session"].started_at = past_start
    ctx["session"].duration_minutes = 30
    ctx["session"].deadline_at = past_deadline
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        with patch("app.services.interview.complete_interview_session_atomic") as mock_complete:
            with pytest.raises(InterviewExpiredError) as exc_info:
                await submit_interview_answer(
                    session=db,
                    session_id=ctx["session_id"],
                    question_id=uuid.uuid4(),
                    organization_id=ctx["org_id"],
                    answer_text="Here is my late response after the deadline",
                )
            assert "Interview duration has expired" in str(exc_info.value)
            mock_complete.assert_called_once()


@pytest.mark.asyncio
async def test_late_question_generation_rejected_when_expired():
    ctx = build_test_context(session_status="IN_PROGRESS")
    past_deadline = datetime.now(timezone.utc) - timedelta(seconds=10)
    ctx["session"].started_at = past_deadline - timedelta(minutes=30)
    ctx["session"].duration_minutes = 30
    ctx["session"].deadline_at = past_deadline
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        with patch("app.services.interview.complete_interview_session_atomic") as mock_complete:
            with pytest.raises(InterviewExpiredError) as exc_info:
                await generate_next_question_for_session(
                    session=db,
                    session_id=ctx["session_id"],
                    organization_id=ctx["org_id"],
                )
            assert "Interview duration has expired" in str(exc_info.value)
            mock_complete.assert_called_once()


# =========================================================================
# 3. Media readiness gate tests before interview starts
# =========================================================================
@pytest.mark.asyncio
async def test_start_interview_blocked_when_media_unverified():
    ctx = build_test_context(session_status="CREATED")
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        with pytest.raises(MediaReadinessRequiredError) as exc_info:
            await start_interview_session(
                session=db,
                session_id=ctx["session_id"],
                organization_id=ctx["org_id"],
                duration_minutes=30,
                media_verified=False,
            )
        assert "verified camera and microphone readiness" in str(exc_info.value)
        assert ctx["session"].status == "CREATED"


# =========================================================================
# 4. Media interruption and recovery timeout (INTERRUPTED_MEDIA_FAILURE)
# =========================================================================
@pytest.mark.asyncio
async def test_media_interruption_completion_saves_reason():
    ctx = build_test_context(session_status="IN_PROGRESS")
    ctx["session"].started_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    ctx["session"].duration_minutes = 30
    ctx["session"].deadline_at = ctx["session"].started_at + timedelta(minutes=30)
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        with patch("app.services.post_interview_scorecard.generate_post_interview_scorecard", new=AsyncMock()):
            with patch("app.services.interview_report.generate_and_persist_interview_report", new=AsyncMock()):
                res = await complete_interview_session_atomic(
                    session=db,
                    session_id=ctx["session_id"],
                    organization_id=ctx["org_id"],
                    reason="INTERRUPTED_MEDIA_FAILURE",
                )
                assert res.status == "COMPLETED"
                assert res.completion_reason == "INTERRUPTED_MEDIA_FAILURE"
                assert res.ended_at is not None


# =========================================================================
# 5. Idempotent completion and single scorecard generation
# =========================================================================
@pytest.mark.asyncio
async def test_scorecard_and_report_generated_exactly_once():
    ctx = build_test_context(session_status="IN_PROGRESS")
    db = setup_mock_db(ctx)

    with patch("app.services.interview.get_tenant_interview_session", return_value=ctx["session"]):
        with patch("app.services.post_interview_scorecard.generate_post_interview_scorecard", new=AsyncMock()) as mock_sc:
            with patch("app.services.interview_report.generate_and_persist_interview_report", new=AsyncMock()) as mock_rep:
                res1 = await complete_interview_session_atomic(
                    session=db,
                    session_id=ctx["session_id"],
                    organization_id=ctx["org_id"],
                    reason="NORMAL",
                )
                assert res1.status == "COMPLETED"
                assert mock_sc.call_count == 1
                assert mock_rep.call_count == 1

                res2 = await complete_interview_session_atomic(
                    session=db,
                    session_id=ctx["session_id"],
                    organization_id=ctx["org_id"],
                    reason="NORMAL",
                )
                assert res2.status == "COMPLETED"
                assert mock_sc.call_count == 1
                assert mock_rep.call_count == 1


# =========================================================================
# 6. Resilient Report Generation (preserving transcript on model failure)
# =========================================================================
@pytest.mark.asyncio
async def test_report_generation_failure_preserves_raw_transcript():
    ctx = build_test_context(session_status="COMPLETED")
    ctx["session"].started_at = datetime.now(timezone.utc) - timedelta(minutes=25)
    ctx["session"].ended_at = datetime.now(timezone.utc)
    ctx["session"].duration_minutes = 30
    ctx["session"].completion_reason = "TIME_EXPIRED"

    mock_messages = [
        InterviewMessage(
            id=uuid.uuid4(),
            session_id=ctx["session_id"],
            role="ai",
            content="Can you explain distributed consensus?",
            sequence_number=1,
            created_at=datetime.now(timezone.utc),
        ),
        InterviewMessage(
            id=uuid.uuid4(),
            session_id=ctx["session_id"],
            role="candidate",
            content="Raft breaks consensus into leader election, log replication, and safety.",
            sequence_number=2,
            created_at=datetime.now(timezone.utc),
        ),
    ]

    mock_media_events = [
        InterviewIntegrityEvent(
            id=uuid.uuid4(),
            interview_session_id=ctx["session_id"],
            event_type="CAMERA_CONNECTED",
            occurred_at=datetime.now(timezone.utc),
            metadata_json={"info": "Webcam ready"},
        ),
        InterviewIntegrityEvent(
            id=uuid.uuid4(),
            interview_session_id=ctx["session_id"],
            event_type="DETECTOR_UNAVAILABLE",
            occurred_at=datetime.now(timezone.utc),
            metadata_json={"reason": "YOLO offline"},
        ),
    ]

    ctx["session"].messages = mock_messages
    ctx["session"].integrity_events = mock_media_events
    db = setup_mock_db(ctx)

    with patch("app.services.interview_report.build_candidate_interview_pre_analysis", side_effect=RuntimeError("AI Model API Quota Exceeded")):
        report_model = await generate_and_persist_interview_report(
            session=db,
            session_id=ctx["session_id"],
            organization_id=ctx["org_id"],
        )

        assert report_model.status == "REPORT_FAILED"
        assert "AI Model API Quota Exceeded" in (report_model.failure_reason or "")
        assert report_model.completion_reason == "TIME_EXPIRED"
        assert report_model.configured_duration_minutes == 30
        assert len(report_model.transcript) == 2
        assert report_model.transcript[0]["content"] == "Can you explain distributed consensus?"
        assert len(report_model.media_events) == 2


# =========================================================================
# 7. Unanswered questions calculation from approved plan
# =========================================================================
@pytest.mark.asyncio
async def test_unanswered_questions_extracted_from_plan():
    ctx = build_test_context(session_status="COMPLETED")
    ctx["session"].started_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    ctx["session"].ended_at = datetime.now(timezone.utc)
    ctx["session"].duration_minutes = 15
    ctx["session"].completion_reason = "TIME_EXPIRED"

    plan = InterviewPlan(
        id=uuid.uuid4(),
        organization_id=ctx["org_id"],
        application_id=ctx["app_id"],
        job_id=ctx["job_id"],
        status="APPROVED",
        version=1,
    )
    round1 = InterviewPlanRound(
        id=uuid.uuid4(),
        plan_id=plan.id,
        round_number=1,
        title="Technical Architecture",
        objective="Assess systems architecture",
        concepts=["Distributed Systems"],
    )
    q1 = InterviewPlanQuestion(
        id=uuid.uuid4(),
        round_id=round1.id,
        sequence=1,
        question_text="How do you handle split brain in clusters?",
        concept="Distributed Systems",
    )
    q2 = InterviewPlanQuestion(
        id=uuid.uuid4(),
        round_id=round1.id,
        sequence=2,
        question_text="Explain database connection pooling locks.",
        concept="Database Concurrency",
    )
    round1.questions = [q1, q2]
    plan.rounds = [round1]

    # Only q1 was asked in session.questions
    asked_q1 = InterviewQuestion(
        id=uuid.uuid4(),
        session_id=ctx["session_id"],
        concept="Distributed Systems",
        question="How do you handle split brain in clusters?",
        sequence_number=1,
    )
    ctx["session"].questions = [asked_q1]

    mock_messages = [
        InterviewMessage(
            id=uuid.uuid4(),
            session_id=ctx["session_id"],
            role="ai",
            content="How do you handle split brain in clusters?",
            sequence_number=1,
            created_at=datetime.now(timezone.utc),
        ),
        InterviewMessage(
            id=uuid.uuid4(),
            session_id=ctx["session_id"],
            role="candidate",
            content="Use quorum fencing and fencing tokens.",
            sequence_number=2,
            created_at=datetime.now(timezone.utc),
        ),
    ]
    ctx["session"].messages = mock_messages
    db = setup_mock_db(ctx, plan=plan)

    with patch("app.services.interview_report.build_candidate_interview_pre_analysis") as mock_ai:
        mock_ai.return_value = MagicMock(
            candidate_strengths=[{"capability_name": "Distributed Systems", "evidence": "Resume project"}],
            candidate_claims=[],
            candidate_unknowns=[],
            potential_risk_areas=[],
            recommended_focus_areas=[],
            key_resume_claims=[],
        )
        rep = await generate_and_persist_interview_report(
            session=db,
            session_id=ctx["session_id"],
            organization_id=ctx["org_id"],
        )
        assert rep.status in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
        assert len(rep.unanswered_questions) == 1
        assert rep.unanswered_questions[0]["question_text"] == "Explain database connection pooling locks."


# =========================================================================
# 8. API endpoints integration tests
# =========================================================================
def test_api_start_interview_with_duration(sync_client):
    ctx = build_test_context(session_status="CREATED")
    app.dependency_overrides[get_current_user] = lambda: ctx["recruiter"]
    token = create_access_token(str(ctx["recruiter"].id))

    try:
        with patch("app.api.interviews.start_interview_session") as mock_start:
            resp_session = InterviewSession(
                id=ctx["session_id"],
                application_id=ctx["app_id"],
                status="IN_PROGRESS",
                current_capability_id=None,
                duration_minutes=15,
                deadline_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                completion_reason=None,
                report_status="NOT_STARTED",
                started_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            mock_start.return_value = resp_session

            response = sync_client.post(
                f"/api/v1/interviews/{ctx['session_id']}/start",
                headers={"Authorization": f"Bearer {token}"},
                json={"duration_minutes": 15, "media_verified": True},
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["duration_minutes"] == 15
            assert data["status"] == "IN_PROGRESS"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_complete_interview_endpoint(sync_client):
    ctx = build_test_context(session_status="IN_PROGRESS")
    app.dependency_overrides[get_current_user] = lambda: ctx["recruiter"]
    token = create_access_token(str(ctx["recruiter"].id))

    try:
        with patch("app.api.interviews.get_tenant_interview_session", return_value=ctx["session"]):
            with patch("app.api.interviews.complete_interview_session_atomic") as mock_complete:
                resp_session = InterviewSession(
                    id=ctx["session_id"],
                    application_id=ctx["app_id"],
                    status="COMPLETED",
                    current_capability_id=None,
                    duration_minutes=30,
                    deadline_at=datetime.now(timezone.utc) + timedelta(minutes=30),
                    completion_reason="TIME_EXPIRED",
                    report_status="COMPLETED",
                    started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
                    ended_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                mock_complete.return_value = resp_session

                response = sync_client.post(
                    f"/api/v1/interviews/{ctx['session_id']}/complete",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"reason": "TIME_EXPIRED"},
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["status"] == "COMPLETED"
                assert data["completion_reason"] == "TIME_EXPIRED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_tenant_isolation(sync_client):
    ctx = build_test_context(session_status="CREATED")
    other_user = User(
        id=uuid.uuid4(),
        organization_id=ctx["other_org_id"],
        email="other.hr@example.com",
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: other_user
    token = create_access_token(str(other_user.id))

    try:
        with patch("app.api.interviews.get_interview_execution_state", side_effect=InterviewSessionNotFoundError("Not found")):
            response = sync_client.get(
                f"/api/v1/interviews/{ctx['session_id']}/state",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND
    finally:
        app.dependency_overrides.pop(get_current_user, None)
