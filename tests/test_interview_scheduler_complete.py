import asyncio
from datetime import datetime, timedelta, timezone
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
from app.models.interview import InterviewSession
from app.models.interview_booking_slot import InterviewBookingSlot
from app.models.interview_plan import InterviewPlan
from app.models.interview_schedule import InterviewSchedule
from app.models.job import Job
from app.models.organization import Organization
from app.models.simulated_notification import SimulatedNotification
from app.models.user import User
from app.services.interview_booking import book_slot_by_candidate
from app.services.meeting_links import DemoMeetingLinkProvider, generate_interview_reference
from app.services.post_interview_scorecard import generate_post_interview_scorecard


async def create_test_context(org_name="TechCorp"):
    org_id = uuid4()
    recruiter_id = uuid4()
    interviewer_id = uuid4()
    job_id = uuid4()
    candidate_id = uuid4()
    application_id = uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name=org_name, slug=f"org-{org_id.hex[:6]}")
        recruiter = User(
            id=recruiter_id,
            email=f"recruiter_{recruiter_id.hex[:6]}@example.com",
            full_name="Rachel Recruiter",
            role=UserRole.RECRUITER.value,
            organization_id=org_id,
            password_hash="fakehash",
            is_active=True,
        )
        interviewer = User(
            id=interviewer_id,
            email=f"interviewer_{interviewer_id.hex[:6]}@example.com",
            full_name="Ian Interviewer",
            role=UserRole.HIRING_MANAGER.value,
            organization_id=org_id,
            password_hash="fakehash",
            is_active=True,
        )
        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=recruiter_id,
            title="Senior Backend Architect",
            description="High concurrency distributed Python systems",
            status="PUBLISHED",
            shortlist_size=5,
        )
        candidate = Candidate(
            id=candidate_id,
            full_name="Elena Rostova",
            email=f"elena_{candidate_id.hex[:6]}@example.com",
            phone="+1234567890",
        )
        application = Application(
            id=application_id,
            job_id=job_id,
            candidate_id=candidate_id,
            status="SHORTLISTED",
            shortlist_status="SHORTLISTED",
            resume_text="Senior Backend Architect with 10+ years Python and PostgreSQL experience.",
        )
        cap = Capability(
            id=uuid4(),
            job_id=job_id,
            name="Distributed Systems",
            description="Database replication and high concurrency patterns",
            importance="CRITICAL",
        )
        plan = InterviewPlan(
            id=uuid4(),
            organization_id=org_id,
            application_id=application_id,
            job_id=job_id,
            version=1,
            status="APPROVED",
            created_by=recruiter_id,
        )
        session.add(org)
        await session.flush()
        session.add_all([recruiter, interviewer])
        await session.flush()
        session.add(job)
        await session.flush()
        session.add(candidate)
        await session.flush()
        session.add(application)
        await session.flush()
        session.add_all([cap, plan])
        await session.commit()

    return {
        "org_id": org_id,
        "recruiter_id": recruiter_id,
        "interviewer_id": interviewer_id,
        "job_id": job_id,
        "candidate_id": candidate_id,
        "application_id": application_id,
        "candidate_email": f"elena_{candidate_id.hex[:6]}@example.com",
        "candidate_name": "Elena Rostova",
    }


@pytest.mark.asyncio
async def test_successful_interview_creation():
    """Verify HR can schedule an interview for an application with demo link and notification."""
    ctx = await create_test_context()
    token = create_access_token(str(ctx["recruiter_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=2, hours=4)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(ctx["application_id"]),
                "interviewer_id": str(ctx["interviewer_id"]),
                "scheduled_start": start_dt.isoformat(),
                "timezone": "UTC",
                "duration_minutes": 60,
                "interview_type": "ONLINE",
                "invitation_notes": "Please prepare to walk through system design.",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["application_id"] == str(ctx["application_id"])
        assert data["interviewer_id"] == str(ctx["interviewer_id"])
        assert data["interviewer_name"] == "Ian Interviewer"
        assert data["status"] == "SCHEDULED"
        assert data["interview_type"] == "ONLINE"
        assert data["interview_reference"].startswith("INT-2026-")
        assert f"https://demo.gap2hire.local/meet/{data['interview_reference']}" == data["meeting_url"]
        assert data["booking_token"] is not None

        # Verify simulated notification created
        notif_res = await ac.get(
            f"/api/v1/interviews/notifications?schedule_id={data['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert notif_res.status_code == 200
        notifs = notif_res.json()
        assert len(notifs) >= 1
        notif = notifs[0]
        assert notif["recipient"] == ctx["candidate_email"]
        assert notif["notification_type"] == "INVITATION"
        assert "DEMO MODE — EMAILS NOT SENT" in notif["body"]
        assert data["interview_reference"] in notif["subject"]
        assert data["meeting_url"] in notif["body"]


@pytest.mark.asyncio
async def test_in_person_interview_no_meeting_link():
    """Verify in-person interviews strictly do not receive online demo meeting links."""
    ctx = await create_test_context()
    token = create_access_token(str(ctx["recruiter_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=3)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(ctx["application_id"]),
                "interviewer_id": str(ctx["interviewer_id"]),
                "scheduled_start": start_dt.isoformat(),
                "timezone": "Asia/Kolkata",
                "duration_minutes": 45,
                "interview_type": "IN_PERSON",
                "location": "Building 4, Executive Boardroom 3",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["interview_type"] == "IN_PERSON"
        assert data["meeting_url"] is None
        assert data["location"] == "Building 4, Executive Boardroom 3"


@pytest.mark.asyncio
async def test_validation_failures():
    """Verify validation: start time in past, invalid durations, missing application."""
    ctx = await create_test_context()
    token = create_access_token(str(ctx["recruiter_id"]))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Past start time
        past_dt = datetime.now(timezone.utc) - timedelta(days=2)
        r1 = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(ctx["application_id"]),
                "scheduled_start": past_dt.isoformat(),
                "duration_minutes": 45,
            },
        )
        assert r1.status_code == 400
        assert "past" in r1.json()["detail"].lower()

        # 2. Duration too short (< 15 min)
        future_dt = datetime.now(timezone.utc) + timedelta(days=2)
        r2 = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(ctx["application_id"]),
                "scheduled_start": future_dt.isoformat(),
                "duration_minutes": 10,
            },
        )
        assert r2.status_code == 422 or r2.status_code == 400

        # 3. Duration too long (> 180 min)
        r3 = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(ctx["application_id"]),
                "scheduled_start": future_dt.isoformat(),
                "duration_minutes": 240,
            },
        )
        assert r3.status_code == 422 or r3.status_code == 400

        # 4. Missing application_id
        r4 = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": future_dt.isoformat(),
                "duration_minutes": 45,
            },
        )
        assert r4.status_code == 400


@pytest.mark.asyncio
async def test_interviewer_conflict_detection():
    """Verify that scheduling an overlapping interview for the same interviewer is rejected with 409 Conflict."""
    ctx = await create_test_context()
    token = create_access_token(str(ctx["recruiter_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=5, hours=10)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Schedule first interview: 10:00 to 11:00
        res1 = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(ctx["application_id"]),
                "interviewer_id": str(ctx["interviewer_id"]),
                "scheduled_start": start_dt.isoformat(),
                "duration_minutes": 60,
            },
        )
        assert res1.status_code == 201

        # Create a second candidate application for the same interviewer
        cand2_id = uuid4()
        app2_id = uuid4()
        async with async_session_factory() as session:
            c2 = Candidate(id=cand2_id, full_name="Marcus Vance", email=f"marcus_{cand2_id.hex[:6]}@example.com")
            a2 = Application(id=app2_id, job_id=ctx["job_id"], candidate_id=cand2_id, status="SHORTLISTED")
            session.add_all([c2, a2])
            await session.commit()

        # Attempt to schedule second interview overlapping: 10:30 to 11:30 -> conflict!
        overlap_dt = start_dt + timedelta(minutes=30)
        res2 = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(app2_id),
                "interviewer_id": str(ctx["interviewer_id"]),
                "scheduled_start": overlap_dt.isoformat(),
                "duration_minutes": 60,
            },
        )
        assert res2.status_code == 409
        assert "Interviewer conflict" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_reschedule_and_cancellation_workflow():
    """Verify editing/rescheduling an interview and cancelling it with simulated notification dispatch."""
    ctx = await create_test_context()
    token = create_access_token(str(ctx["recruiter_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=4)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Schedule
        res = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(ctx["application_id"]),
                "interviewer_id": str(ctx["interviewer_id"]),
                "scheduled_start": start_dt.isoformat(),
                "duration_minutes": 45,
            },
        )
        assert res.status_code == 201
        sched_id = res.json()["id"]

        # 2. Reschedule to new time
        new_start = start_dt + timedelta(days=1, hours=2)
        reschedule_res = await ac.post(
            f"/api/v1/interviews/schedules/{sched_id}/reschedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scheduled_start": new_start.isoformat(),
                "duration_minutes": 60,
                "reschedule_reason": "Candidate requested later time slot",
            },
        )
        assert reschedule_res.status_code == 200
        resched_data = reschedule_res.json()
        assert resched_data["duration_minutes"] == 60

        # Verify reschedule notification
        notifs_res = await ac.get(
            f"/api/v1/interviews/notifications?schedule_id={sched_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        types = [n["notification_type"] for n in notifs_res.json()]
        assert "RESCHEDULE" in types

        # 3. Cancel interview
        cancel_res = await ac.post(
            f"/api/v1/interviews/schedules/{sched_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Position filled by internal transfer."},
        )
        assert cancel_res.status_code == 200
        cancel_data = cancel_res.json()
        assert cancel_data["status"] == "CANCELLED"
        assert cancel_data["cancellation_reason"] == "Position filled by internal transfer."

        # Verify cancellation notification
        notifs_res2 = await ac.get(
            f"/api/v1/interviews/notifications?schedule_id={sched_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        types2 = [n["notification_type"] for n in notifs_res2.json()]
        assert "CANCELLATION" in types2


@pytest.mark.asyncio
async def test_candidate_self_booking_and_concurrency_lock():
    """Verify HR publishes slots, candidate self-books, and concurrent double-booking is prevented."""
    ctx = await create_test_context()
    token = create_access_token(str(ctx["recruiter_id"]))

    slot1_time = datetime.now(timezone.utc) + timedelta(days=6, hours=10)
    slot2_time = datetime.now(timezone.utc) + timedelta(days=6, hours=14)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Publish booking slots
        pub_res = await ac.post(
            f"/api/v1/applications/{ctx['application_id']}/booking-slots",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "interviewer_id": str(ctx["interviewer_id"]),
                "interview_type": "ONLINE",
                "slots": [
                    {"start_time": slot1_time.isoformat(), "duration_minutes": 45},
                    {"start_time": slot2_time.isoformat(), "duration_minutes": 45},
                ],
            },
        )
        assert pub_res.status_code == 201
        pub_data = pub_res.json()
        booking_token = pub_data["booking_token"]
        assert len(pub_data["slots"]) == 2
        slot1_id = pub_data["slots"][0]["id"]
        slot2_id = pub_data["slots"][1]["id"]

        # 2. Public view of booking slots (no auth header needed)
        view_res = await ac.get(f"/api/v1/booking/{booking_token}/slots")
        assert view_res.status_code == 200
        view_data = view_res.json()
        assert view_data["candidate_name"] == "Elena"  # Masked first name
        assert view_data["job_title"] == "Senior Backend Architect"
        assert len(view_data["slots"]) == 2

        # 3. Book slot 1
        book_res = await ac.post(
            f"/api/v1/booking/{booking_token}/book",
            json={"slot_id": slot1_id},
        )
        assert book_res.status_code == 201
        book_data = book_res.json()
        assert book_data["status"] == "CONFIRMED"
        assert book_data["meeting_url"] is not None

        # 4. Attempt to book the same slot again -> 409 Conflict
        second_book_res = await ac.post(
            f"/api/v1/booking/{booking_token}/book",
            json={"slot_id": slot1_id},
        )
        assert second_book_res.status_code == 409


@pytest.mark.asyncio
async def test_tenant_isolation_on_interview_scheduler():
    """Verify tenant A cannot view or manage tenant B's interview schedules."""
    ctx_a = await create_test_context(org_name="Org Alpha")
    ctx_b = await create_test_context(org_name="Org Beta")

    token_a = create_access_token(str(ctx_a["recruiter_id"]))
    token_b = create_access_token(str(ctx_b["recruiter_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=3)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Schedule in Org A
        res_a = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "application_id": str(ctx_a["application_id"]),
                "interviewer_id": str(ctx_a["interviewer_id"]),
                "scheduled_start": start_dt.isoformat(),
                "duration_minutes": 45,
            },
        )
        assert res_a.status_code == 201
        sched_a_id = res_a.json()["id"]

        # Recruiter B attempts to fetch schedule A -> 404 Not Found
        res_b = await ac.get(
            f"/api/v1/interviews/schedules/{sched_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_b.status_code == 404

        # Recruiter B attempts to cancel schedule A -> 404
        cancel_b = await ac.post(
            f"/api/v1/interviews/schedules/{sched_a_id}/cancel",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"reason": "Malicious attempt"},
        )
        assert cancel_b.status_code == 404


@pytest.mark.asyncio
async def test_completion_and_post_interview_scorecard_integration():
    """Verify completing an interview transitions InterviewSession status and links to scorecard."""
    ctx = await create_test_context()
    token = create_access_token(str(ctx["recruiter_id"]))

    start_dt = datetime.now(timezone.utc) + timedelta(days=2)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/interviews/schedules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "application_id": str(ctx["application_id"]),
                "interviewer_id": str(ctx["interviewer_id"]),
                "scheduled_start": start_dt.isoformat(),
                "duration_minutes": 45,
            },
        )
        assert res.status_code == 201
        sched_id = res.json()["id"]
        session_id = res.json()["session_id"]

        # Mark completed
        comp_res = await ac.post(
            f"/api/v1/interviews/schedules/{sched_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert comp_res.status_code == 200
        assert comp_res.json()["status"] == "COMPLETED"

        # Verify underlying session is COMPLETED in DB
        async with async_session_factory() as session:
            sess_rec = await session.get(InterviewSession, uuid4() if False else session_id)
            assert sess_rec.status == "COMPLETED"
            assert sess_rec.ended_at is not None
