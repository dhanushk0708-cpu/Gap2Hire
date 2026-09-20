from datetime import datetime
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.roles import UserRole
from app.core.security import create_access_token
from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.imported_email import ImportedEmail
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.schemas.email_integration import EmailAttachment, NormalizedEmail
from app.services.email_intake import batch_sync_emails, process_email_intake
from app.services.interview import (
    CandidateNotShortlistedError,
    create_interview_session,
    start_interview_session,
)

SAMPLE_RESUME_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Length 85 >>\nstream\n"
    b"BT /F1 12 Tf 72 712 Td (5 years of FastAPI, PostgreSQL, and distributed caching with Redis) Tj ET\n"
    b"endstream\nendobj\nxref\n0 5\n0000000000 65535 f \n"
    b"0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n0000000201 00000 n \n"
    b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n337\n%%EOF"
)


async def setup_test_environment():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name="HR Workflow Org", slug=f"hr-{uuid.uuid4().hex[:6]}")
        session.add(org)
        await session.flush()

        user = User(
            id=user_id,
            organization_id=org_id,
            email=f"hr-{uuid.uuid4().hex[:6]}@workflow.test",
            password_hash="hash",
            full_name="HR Workflow Manager",
            role=UserRole.HIRING_MANAGER.value,
        )
        session.add(user)
        await session.flush()

        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Senior Backend Engineer",
            description="FastAPI, PostgreSQL",
            status="PUBLISHED",
        )
        session.add(job)
        await session.flush()

        cap1 = Capability(id=uuid.uuid4(), job_id=job_id, name="FastAPI", description="FastAPI", importance="HIGH")
        cap2 = Capability(id=uuid.uuid4(), job_id=job_id, name="PostgreSQL", description="PostgreSQL", importance="HIGH")
        session.add_all([cap1, cap2])
        await session.commit()

    token = create_access_token(str(user_id))

    return {
        "org_id": org_id,
        "user_id": user_id,
        "job_id": job_id,
        "token": token,
    }


# 1. New email imported
@pytest.mark.asyncio
async def test_new_email_imported():
    env = await setup_test_environment()
    msg_id = f"gmail-new-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"candidate-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="New Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="Applying for Senior Backend Engineer.",
        received_at=datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-1",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        result = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )

        assert result.intake_status == "PROCESSED"
        assert result.candidate_id is not None
        assert result.application_id is not None

        # Verify ImportedEmail record exists in DB
        imported_stmt = select(ImportedEmail).where(
            ImportedEmail.organization_id == env["org_id"],
            ImportedEmail.external_message_id == msg_id,
        )
        imported_rec = await session.scalar(imported_stmt)
        assert imported_rec is not None
        assert imported_rec.status == "PROCESSED"
        assert imported_rec.candidate_id == result.candidate_id


# 2. Same email synchronized twice -> no duplicate candidates or applications
@pytest.mark.asyncio
async def test_same_email_synchronized_twice_no_duplicate():
    env = await setup_test_environment()
    msg_id = f"gmail-dup-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"candidate-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="Duplicate Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="Applying for Senior Backend Engineer.",
        received_at=datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-dup",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        # First sync
        res1 = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )
        assert res1.intake_status == "PROCESSED"

        # Second sync
        res2 = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )
        assert res2.intake_status == "SKIPPED"
        assert res2.candidate_id == res1.candidate_id
        assert res2.application_id == res1.application_id
        assert "already processed" in res2.reason.lower()


# 3. Already processed email -> skipped in batch sync
@pytest.mark.asyncio
async def test_already_processed_email_skipped_in_batch():
    env = await setup_test_environment()

    async with async_session_factory() as session:
        # Sync batch 1
        res1 = await batch_sync_emails(
            session=session,
            organization_id=env["org_id"],
            limit=5,
            target_job_id=env["job_id"],
        )
        assert res1.emails_fetched == 5
        assert res1.duplicates_skipped == 0

        # Sync same batch again
        res2 = await batch_sync_emails(
            session=session,
            organization_id=env["org_id"],
            limit=5,
            target_job_id=env["job_id"],
        )
        assert res2.emails_fetched == 5
        assert res2.duplicates_skipped == 5


# 4. Unread email -> imported
@pytest.mark.asyncio
async def test_unread_email_imported():
    env = await setup_test_environment()
    msg_id = f"gmail-unread-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"unread-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="Unread Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="Unread application email.",
        received_at=datetime.utcnow(),
        metadata={"is_unread": True},
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-unread",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        res = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )
        assert res.intake_status == "PROCESSED"
        assert res.candidate_id is not None


# 5. Read but never processed email -> can be imported
@pytest.mark.asyncio
async def test_read_but_never_processed_email_imported():
    env = await setup_test_environment()
    msg_id = f"gmail-read-never-processed-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"read-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="Read Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="Read application email.",
        received_at=datetime.utcnow(),
        metadata={"is_unread": False},
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-read",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        res = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )
        assert res.intake_status == "PROCESSED"
        assert res.candidate_id is not None


# 6. Candidate enters screening queue API
@pytest.mark.asyncio
async def test_candidate_enters_screening_queue_api():
    env = await setup_test_environment()
    msg_id = f"gmail-queue-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"queue-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="Queue Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="FastAPI and PostgreSQL engineer.",
        received_at=datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-q",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/jobs/{env['job_id']}/screening-queue",
            headers={"Authorization": f"Bearer {env['token']}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        cand = next(c for c in data if c["candidate_name"] == "Queue Candidate")
        assert cand["status"] in ("SCREENING", "APPLIED")
        assert cand["shortlist_status"] == "PENDING"


# 7. Screening executes (RUN SCREENING HR Action)
@pytest.mark.asyncio
async def test_run_screening_hr_action():
    env = await setup_test_environment()
    msg_id = f"gmail-run-screen-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"screen-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="Screen Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="FastAPI backend engineer.",
        received_at=datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-s",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        intake_res = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )
        app_id = intake_res.application_id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger explicit RUN SCREENING
        response = await client.post(
            f"/api/v1/applications/{app_id}/run-screening",
            headers={"Authorization": f"Bearer {env['token']}"},
        )
        assert response.status_code == 200
        report = response.json()
        assert report["application_id"] == str(app_id)
        assert report["candidate_name"] == "Screen Candidate"
        assert len(report["requirements_evaluated"]) >= 2
        assert "score" not in report


# 8. Shortlist required before interview
@pytest.mark.asyncio
async def test_shortlist_required_before_interview():
    env = await setup_test_environment()
    msg_id = f"gmail-gate-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"pending-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="Pending Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="FastAPI backend engineer.",
        received_at=datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-p",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        intake_res = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )
        app_id = intake_res.application_id

    # Try creating interview while shortlist_status is PENDING
    async with async_session_factory() as session:
        with pytest.raises(CandidateNotShortlistedError):
            await create_interview_session(
                session=session,
                application_id=app_id,
                organization_id=env["org_id"],
            )


# 9. Not-shortlisted candidate blocked
@pytest.mark.asyncio
async def test_not_shortlisted_candidate_blocked():
    env = await setup_test_environment()
    msg_id = f"gmail-rej-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"rejected-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="Rejected Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="FastAPI backend engineer.",
        received_at=datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-r",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        intake_res = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )
        app_id = intake_res.application_id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Mark candidate NOT_SHORTLISTED
        shortlist_res = await client.patch(
            f"/api/v1/applications/{app_id}/shortlist",
            json={"decision": "NOT_SHORTLISTED", "reason": "Lacks required cloud experience"},
            headers={"Authorization": f"Bearer {env['token']}"},
        )
        assert shortlist_res.status_code == 200

        # Attempt to start interview via API -> must fail with 400
        interview_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers={"Authorization": f"Bearer {env['token']}"},
        )
        assert interview_res.status_code == 400
        assert "not shortlisted" in interview_res.json()["detail"].lower() or "not_shortlisted" in interview_res.json()["detail"].lower()


# 10. Shortlisted candidate allowed to start interview
@pytest.mark.asyncio
async def test_shortlisted_candidate_allowed_to_start_interview():
    env = await setup_test_environment()
    msg_id = f"gmail-shortlisted-{uuid.uuid4().hex[:8]}"

    incoming = NormalizedEmail(
        external_id=msg_id,
        provider="GMAIL",
        sender_email=f"shortlisted-{uuid.uuid4().hex[:6]}@example.com",
        sender_name="Shortlisted Candidate",
        recipient_emails=["jobs@company.com"],
        subject="Application for Senior Backend Engineer",
        body_text="FastAPI backend engineer.",
        received_at=datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-sl",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        intake_res = await process_email_intake(
            session=session,
            email=incoming,
            organization_id=env["org_id"],
            target_job_id=env["job_id"],
        )
        app_id = intake_res.application_id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Shortlist candidate
        shortlist_res = await client.patch(
            f"/api/v1/applications/{app_id}/shortlist",
            json={"decision": "SHORTLISTED", "reason": "Strong Python background"},
            headers={"Authorization": f"Bearer {env['token']}"},
        )
        assert shortlist_res.status_code == 200

        # Create interview session
        interview_res = await client.post(
            f"/api/v1/applications/{app_id}/interviews",
            headers={"Authorization": f"Bearer {env['token']}"},
        )
        assert interview_res.status_code == 201
        session_data = interview_res.json()
        sess_id = session_data["id"]

        # Start interview session
        start_res = await client.patch(
            f"/api/v1/interviews/{sess_id}/start",
            headers={"Authorization": f"Bearer {env['token']}"},
        )
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "IN_PROGRESS"


# 11. HR Live Interview Observer Snapshot Endpoint
@pytest.mark.asyncio
async def test_hr_live_interview_observer_snapshot():
    env = await setup_test_environment()
    app_id = uuid.uuid4()
    session_id = uuid.uuid4()

    async with async_session_factory() as session:
        cand = Candidate(id=uuid.uuid4(), full_name="Live Cand", email="live@test.com")
        session.add(cand)
        await session.flush()

        app_obj = Application(
            id=app_id,
            candidate_id=cand.id,
            job_id=env["job_id"],
            status="INTERVIEW",
            shortlist_status="SHORTLISTED",
        )
        session.add(app_obj)
        await session.flush()

        int_sess = InterviewSession(
            id=session_id,
            application_id=app_id,
            status="IN_PROGRESS",
        )
        session.add(int_sess)
        await session.flush()

        caps_stmt = select(Capability).where(Capability.job_id == env["job_id"]).limit(1)
        cap = await session.scalar(caps_stmt)

        q = InterviewQuestion(
            id=uuid.uuid4(),
            session_id=session_id,
            capability_id=cap.id,
            question="How do you structure async FastAPI endpoints?",
            answer="I use async def and async SQLAlchemy sessions.",
            sequence_number=1,
        )
        session.add(q)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/interviews/{session_id}/hr-live",
            headers={"Authorization": f"Bearer {env['token']}"},
        )
        assert response.status_code == 200
        live_data = response.json()
        assert live_data["session_id"] == str(session_id)
        assert live_data["status"] == "IN_PROGRESS"
        assert live_data["current_question"] == "How do you structure async FastAPI endpoints?"
        assert live_data["candidate_answer"] == "I use async def and async SQLAlchemy sessions."
        assert live_data["is_read_only"] is True

