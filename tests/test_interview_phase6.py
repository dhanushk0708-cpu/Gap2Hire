from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.roles import UserRole
from app.core.security import create_access_token
from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.email_connection import EmailConnection
from app.models.interview import InterviewSession
from app.models.interview_dataset import (
    InterviewDatasetFile,
    InterviewDatasetQuestion,
    InterviewQuestionDataset,
)
from app.models.interview_plan import (
    InterviewPlan,
    InterviewPlanQuestion,
    InterviewPlanRound,
)
from app.models.interview_schedule import InterviewSchedule
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.services.interview_scheduling import (
    format_candidate_invitation_email,
    get_interview_schedule,
    schedule_interview_for_session,
)


async def setup_phase6_test_data(is_approved: bool = True):
    org_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()
    cand_id = uuid4()
    app_id = uuid4()
    dataset_file_id = uuid4()
    dataset_id = uuid4()
    plan_id = uuid4()
    round_id = uuid4()
    pq1_id = uuid4()
    session_id = uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name="Acme Scheduling Corp", slug=f"acme-{org_id.hex[:6]}")
        user = User(
            id=user_id,
            email=f"recruiter_{user_id.hex[:6]}@example.com",
            full_name="Alex Recruiter",
            role=UserRole.RECRUITER.value,
            organization_id=org_id,
            password_hash="fakehash",
            is_active=True,
        )
        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Senior Platform Engineer",
            description="Distributed systems and Kubernetes infrastructure",
            status="PUBLISHED",
            shortlist_size=5,
        )
        cand = Candidate(
            id=cand_id,
            full_name="Samantha Ray",
            email=f"samantha_{cand_id.hex[:6]}@example.com",
        )
        application = Application(
            id=app_id,
            job_id=job_id,
            candidate_id=cand_id,
            status="SHORTLISTED",
            shortlist_status="SHORTLISTED",
            resume_text="Senior Platform Engineer with extensive Go and Kubernetes experience.",
        )
        cap1 = Capability(
            id=uuid4(),
            job_id=job_id,
            name="Kubernetes & Go",
            description="Operator design and distributed consensus",
            importance="CRITICAL",
        )
        dataset_file = InterviewDatasetFile(
            id=dataset_file_id,
            organization_id=org_id,
            job_id=job_id,
            filename="phase6_dataset.xlsx",
            file_hash="hash_p6_123",
            total_questions=1,
            created_by=user_id,
        )
        dataset = InterviewQuestionDataset(
            id=dataset_id,
            file_id=dataset_file_id,
            organization_id=org_id,
            name="Platform Engineering",
            concept="Kubernetes",
            question_count=1,
        )
        dq1 = InterviewDatasetQuestion(
            id=uuid4(),
            dataset_id=dataset_id,
            organization_id=org_id,
            question_text="How do Kubernetes controllers reconcile desired state with CRDs?",
            concept="Kubernetes",
            difficulty="HARD",
            question_type="ARCHITECTURE",
        )

        plan = InterviewPlan(
            id=plan_id,
            organization_id=org_id,
            application_id=app_id,
            job_id=job_id,
            dataset_file_id=dataset_file_id,
            status="APPROVED" if is_approved else "DRAFT",
            version=1,
            approved_by=user_id if is_approved else None,
        )
        round1 = InterviewPlanRound(
            id=round_id,
            plan_id=plan_id,
            round_number=1,
            title="Architecture & Consensus",
            objective="Evaluate Kubernetes Operator architecture",
            concepts=["Kubernetes"],
            sequence=1,
        )
        pq1 = InterviewPlanQuestion(
            id=pq1_id,
            round_id=round_id,
            dataset_question_id=dq1.id,
            question_text="How do Kubernetes controllers reconcile desired state with CRDs?",
            concept="Kubernetes",
            difficulty="HARD",
            question_type="ARCHITECTURE",
            sequence=1,
        )

        interview_session = InterviewSession(
            id=session_id,
            application_id=app_id,
            status="IN_PROGRESS",
        )

        session.add(org)
        session.add(user)
        await session.flush()

        session.add(job)
        session.add(cand)
        await session.flush()

        session.add(cap1)
        session.add(application)
        session.add(dataset_file)
        await session.flush()

        session.add(dataset)
        session.add(dq1)
        session.add(plan)
        await session.flush()

        session.add(round1)
        await session.flush()

        session.add(pq1)
        await session.flush()

        session.add(interview_session)
        await session.commit()

    return {
        "org_id": org_id,
        "user_id": user_id,
        "job_id": job_id,
        "cand_id": cand_id,
        "app_id": app_id,
        "plan_id": plan_id,
        "session_id": session_id,
        "cand_name": "Samantha Ray",
        "cand_email": f"samantha_{cand_id.hex[:6]}@example.com",
        "job_title": "Senior Platform Engineer",
    }


@pytest.mark.asyncio
async def test_approved_plan_can_be_scheduled():
    """Verify an approved plan session can be scheduled with Google Meet link and candidate email."""
    setup = await setup_phase6_test_data(is_approved=True)
    token = create_access_token(str(setup["user_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=2, hours=3)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": start_dt.isoformat(),
                "timezone": "America/New_York",
                "duration_minutes": 45,
                "invitation_notes": "Please prepare for system architecture whiteboard discussion.",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["session_id"] == str(setup["session_id"])
        assert data["status"] == "SCHEDULED"
        assert "meet.google.com" in data["meeting_url"]
        assert data["duration_minutes"] == 45
        assert data["timezone"] == "America/New_York"
        assert data["candidate_email_sent"] is True
        assert data["candidate_name"] == setup["cand_name"]


@pytest.mark.asyncio
async def test_unapproved_plan_rejected():
    """Verify scheduling is rejected if the interview plan is unapproved."""
    setup = await setup_phase6_test_data(is_approved=False)
    token = create_access_token(str(setup["user_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=1)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": start_dt.isoformat(),
                "timezone": "UTC",
                "duration_minutes": 45,
            },
        )
        assert res.status_code == 400
        assert "No approved interview plan" in res.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_datetime_rejected():
    """Verify invalid start time (in the past) or invalid duration is rejected."""
    setup = await setup_phase6_test_data(is_approved=True)
    token = create_access_token(str(setup["user_id"]))

    # 1. Past start time
    past_dt = datetime.now(timezone.utc) - timedelta(days=3)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": past_dt.isoformat(),
                "timezone": "UTC",
                "duration_minutes": 45,
            },
        )
        assert res1.status_code == 400
        assert "past" in res1.json()["detail"].lower()

        # 2. Invalid duration (< 15 mins)
        future_dt = datetime.now(timezone.utc) + timedelta(days=1)
        res2 = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": future_dt.isoformat(),
                "timezone": "UTC",
                "duration_minutes": 5,
            },
        )
        assert res2.status_code in (400, 422)


@pytest.mark.asyncio
async def test_duplicate_scheduling_prevented():
    """Verify scheduling an already scheduled interview session returns 409 Conflict."""
    setup = await setup_phase6_test_data(is_approved=True)
    token = create_access_token(str(setup["user_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=2)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First scheduling succeeds
        res1 = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": start_dt.isoformat(),
                "timezone": "UTC",
                "duration_minutes": 60,
            },
        )
        assert res1.status_code == 201

        # Second scheduling attempt is rejected
        res2 = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": (start_dt + timedelta(days=1)).isoformat(),
                "timezone": "UTC",
                "duration_minutes": 60,
            },
        )
        assert res2.status_code == 409
        assert "already scheduled" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_scheduling_persisted():
    """Verify schedule record is persisted in DB and retrievable via GET endpoint."""
    setup = await setup_phase6_test_data(is_approved=True)
    token = create_access_token(str(setup["user_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=3)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        post_res = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": start_dt.isoformat(),
                "timezone": "Europe/London",
                "duration_minutes": 45,
            },
        )
        assert post_res.status_code == 201

        # Retrieve schedule
        get_res = await ac.get(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["session_id"] == str(setup["session_id"])
        assert get_data["timezone"] == "Europe/London"
        assert get_data["status"] == "SCHEDULED"
        assert get_data["meeting_url"] == post_res.json()["meeting_url"]


@pytest.mark.asyncio
async def test_candidate_email_payload_contains_meeting_details():
    """Verify the invitation email payload contains candidate name, job title, date, time, and Meet URL."""
    start_dt = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
    meet_url = "https://meet.google.com/gap-abc-def"

    email_data = format_candidate_invitation_email(
        candidate_name="Samantha Ray",
        job_title="Senior Platform Engineer",
        organization_name="Acme Corp",
        scheduled_start=start_dt,
        duration_minutes=45,
        timezone_name="UTC",
        meeting_url=meet_url,
        invitation_notes="Bring your favorite IDE.",
    )

    assert "Samantha Ray" in email_data["body"]
    assert "Senior Platform Engineer" in email_data["subject"]
    assert "Acme Corp" in email_data["subject"]
    assert "Thursday, October 15, 2026" in email_data["body"]
    assert "02:00 PM" in email_data["body"]
    assert "45 minutes" in email_data["body"]
    assert meet_url in email_data["body"]
    assert "Bring your favorite IDE." in email_data["body"]
    assert "JOINING INSTRUCTIONS" in email_data["body"]


@pytest.mark.asyncio
async def test_tenant_isolation_on_scheduling():
    """Verify unauthorized organization cannot schedule or view schedule of another organization's session."""
    setup = await setup_phase6_test_data(is_approved=True)

    # Create other tenant recruiter
    other_org_id = uuid4()
    other_user_id = uuid4()
    async with async_session_factory() as session:
        other_org = Organization(id=other_org_id, name="Other Org", slug=f"oth-{other_org_id.hex[:6]}")
        other_user = User(
            id=other_user_id,
            email=f"intruder_{other_user_id.hex[:6]}@example.com",
            full_name="Other Recruiter",
            role=UserRole.RECRUITER.value,
            organization_id=other_org_id,
            password_hash="fakehash",
            is_active=True,
        )
        session.add(other_org)
        session.add(other_user)
        await session.commit()

    other_token = create_access_token(str(other_user_id))
    start_dt = datetime.now(timezone.utc) + timedelta(days=2)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Schedule attempt by other tenant -> 404
        post_res = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {other_token}"},
            json={
                "scheduled_start": start_dt.isoformat(),
                "timezone": "UTC",
                "duration_minutes": 45,
            },
        )
        assert post_res.status_code == 404

        # Read attempt by other tenant -> 404
        get_res = await ac.get(
            f"/api/v1/interviews/{setup['session_id']}/schedule",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_existing_gmail_integration_remains_functional():
    """Verify existing Gmail OAuth URL generation and token helper remain intact."""
    from app.services.gmail_provider import (
        DEFAULT_REDIRECT_URI,
        get_google_auth_url,
        get_google_redirect_uri,
        load_google_oauth_config,
    )

    auth_url = get_google_auth_url(state="test-state-123")
    assert "https://accounts.google.com" in auth_url
    assert "state=test-state-123" in auth_url
    assert "gmail.readonly" in auth_url

    cfg = load_google_oauth_config()
    assert isinstance(cfg, dict)
    redirect_uri = get_google_redirect_uri(cfg)
    assert redirect_uri is not None
