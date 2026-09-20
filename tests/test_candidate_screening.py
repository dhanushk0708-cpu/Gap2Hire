import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview_round import InterviewRound
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.schemas.email_integration import EmailAttachment, NormalizedEmail
from app.services.email_intake import process_email_intake
from app.services.interview import (
    CandidateNotShortlistedError,
    create_interview_session,
    start_interview_session,
)
from app.services.screening import (
    ApplicationNotFoundError,
    apply_shortlist_decision,
    build_candidate_screening_report,
    evaluate_candidate_eligibility,
    list_job_candidates_with_screening,
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


async def setup_test_org_job_and_candidate():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    app_id = uuid.uuid4()
    cap_fastapi_id = uuid.uuid4()
    cap_postgres_id = uuid.uuid4()
    cap_k8s_id = uuid.uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name="Screening Test Org", slug=f"org-{uuid.uuid4().hex[:6]}")
        session.add(org)
        await session.flush()

        user = User(
            id=user_id,
            organization_id=org_id,
            email=f"recruiter-{uuid.uuid4().hex[:6]}@screening.test",
            password_hash="hash",
            full_name="Lead Recruiter",
            role="COMPANY_ADMIN",
        )
        session.add(user)
        await session.flush()

        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Senior Backend Engineer",
            description="FastAPI, PostgreSQL, and Kubernetes architecture",
            status="PUBLISHED",
        )
        session.add(job)
        await session.flush()

        # Capabilities
        c1 = Capability(id=cap_fastapi_id, job_id=job_id, name="FastAPI", description="FastAPI REST", importance="HIGH")
        c2 = Capability(id=cap_postgres_id, job_id=job_id, name="PostgreSQL", description="Database design", importance="HIGH")
        c3 = Capability(id=cap_k8s_id, job_id=job_id, name="Kubernetes", description="K8s cluster ops", importance="HIGH")
        session.add_all([c1, c2, c3])
        await session.flush()

        # Interview round
        rnd = InterviewRound(id=uuid.uuid4(), job_id=job_id, name="Technical Round", round_type="TECHNICAL", sequence=1)
        session.add(rnd)

        # Candidate
        cand = Candidate(id=cand_id, full_name="Jane Doe", email=f"jane.{uuid.uuid4().hex[:6]}@example.com")
        session.add(cand)
        await session.flush()

        # Application
        app_obj = Application(
            id=app_id,
            candidate_id=cand_id,
            job_id=job_id,
            status="APPLIED",
            screening_status="PENDING",
            shortlist_status="PENDING",
            resume_text="5 years of FastAPI and PostgreSQL backend development.",
        )
        session.add(app_obj)
        await session.flush()

        # Evidence: FastAPI & PostgreSQL claims
        e1 = Evidence(
            application_id=app_id,
            capability_id=cap_fastapi_id,
            source_type="RESUME",
            content="Built high-throughput REST microservices in FastAPI",
            strength="STRONG",
            provenance="CLAIM",
        )
        e2 = Evidence(
            application_id=app_id,
            capability_id=cap_postgres_id,
            source_type="RESUME",
            content="Optimized PostgreSQL queries and indexing",
            strength="STRONG",
            provenance="CLAIM",
        )
        session.add_all([e1, e2])
        await session.commit()

    return {
        "org_id": org_id,
        "job_id": job_id,
        "cand_id": cand_id,
        "app_id": app_id,
        "caps": [c1, c2, c3],
    }


# 1. Eligibility evaluation with unknown requirement (never automatic failure)
@pytest.mark.asyncio
async def test_eligibility_evaluation_with_unknown_requirement():
    env = await setup_test_org_job_and_candidate()

    async with async_session_factory() as session:
        job = await session.get(Job, env["job_id"])
        application = await session.get(Application, env["app_id"])
        caps_stmt = select(Capability).where(Capability.job_id == env["job_id"])
        capabilities = list((await session.scalars(caps_stmt)).all())
        ev_stmt = select(Evidence).where(Evidence.application_id == env["app_id"])
        evidence_list = list((await session.scalars(ev_stmt)).all())

        status, evaluations = await evaluate_candidate_eligibility(
            job=job,
            application=application,
            capabilities=capabilities,
            evidence_list=evidence_list,
        )

        assert status == "NEEDS_REVIEW"
        assert len(evaluations) == 3

        fastapi_eval = next(e for e in evaluations if e.requirement_name == "FastAPI")
        assert fastapi_eval.status == "MET"
        assert fastapi_eval.provenance == "CLAIM"

        k8s_eval = next(e for e in evaluations if e.requirement_name == "Kubernetes")
        assert k8s_eval.status == "UNKNOWN"
        assert k8s_eval.provenance == "UNKNOWN"


# 2. Candidate screening report structure (no unexplained score, no auto hiring decision)
@pytest.mark.asyncio
async def test_candidate_screening_report_structure():
    env = await setup_test_org_job_and_candidate()

    async with async_session_factory() as session:
        report = await build_candidate_screening_report(
            session=session,
            application_id=env["app_id"],
            organization_id=env["org_id"],
        )

        assert report.application_id == env["app_id"]
        assert report.candidate_name == "Jane Doe"
        assert len(report.claims_summary) == 2
        assert "Kubernetes" in report.unknowns_summary
        assert len(report.missing_information) >= 1
        assert any("FastAPI" in c for c in report.claims_summary)
        assert "Kubernetes" in report.summary_explanation
        assert "score" not in report.model_dump()


# 3. Shortlist decision workflow (Human HR Decision)
@pytest.mark.asyncio
async def test_shortlist_decision_workflow():
    env = await setup_test_org_job_and_candidate()

    async with async_session_factory() as session:
        res = await apply_shortlist_decision(
            session=session,
            application_id=env["app_id"],
            organization_id=env["org_id"],
            decision="SHORTLISTED",
            reason="Strong FastAPI and PostgreSQL claims. Will probe Kubernetes in technical round.",
        )

        assert res.status == "SHORTLISTED"
        assert res.shortlist_status == "SHORTLISTED"
        assert res.is_interview_ready is True
        assert res.shortlisted_at is not None

        # Verify persisted in database
        app_obj = await session.get(Application, env["app_id"])
        assert app_obj.status == "SHORTLISTED"
        assert app_obj.shortlist_status == "SHORTLISTED"


# 4. Not shortlisted decision workflow
@pytest.mark.asyncio
async def test_not_shortlisted_decision_workflow():
    env = await setup_test_org_job_and_candidate()

    async with async_session_factory() as session:
        res = await apply_shortlist_decision(
            session=session,
            application_id=env["app_id"],
            organization_id=env["org_id"],
            decision="NOT_SHORTLISTED",
            reason="Missing critical container orchestration background.",
        )

        assert res.status == "NOT_SHORTLISTED"
        assert res.shortlist_status == "NOT_SHORTLISTED"
        assert res.is_interview_ready is False


# 5. Interview blocked for NOT_SHORTLISTED candidates
@pytest.mark.asyncio
async def test_interview_blocked_for_not_shortlisted_candidate():
    env = await setup_test_org_job_and_candidate()

    async with async_session_factory() as session:
        # Mark candidate NOT_SHORTLISTED
        await apply_shortlist_decision(
            session=session,
            application_id=env["app_id"],
            organization_id=env["org_id"],
            decision="NOT_SHORTLISTED",
            reason="Rejected at screening",
        )

        # Attempt to create interview session -> Blocked server-side
        with pytest.raises(CandidateNotShortlistedError):
            await create_interview_session(
                session=session,
                application_id=env["app_id"],
                organization_id=env["org_id"],
            )


# 6. Shortlisted candidate can start interview
@pytest.mark.asyncio
async def test_shortlisted_candidate_can_start_interview():
    env = await setup_test_org_job_and_candidate()

    async with async_session_factory() as session:
        # Shortlist candidate
        await apply_shortlist_decision(
            session=session,
            application_id=env["app_id"],
            organization_id=env["org_id"],
            decision="SHORTLISTED",
            reason="Approved for interview",
        )

        # Create session -> Allowed
        sess = await create_interview_session(
            session=session,
            application_id=env["app_id"],
            organization_id=env["org_id"],
        )
        assert sess.status == "CREATED"

        # Start session -> Allowed
        started_sess = await start_interview_session(
            session=session,
            session_id=sess.id,
            organization_id=env["org_id"],
        )
        assert started_sess.status == "IN_PROGRESS"


# 7. Job candidates screening list endpoint
@pytest.mark.asyncio
async def test_job_candidates_screening_list():
    env = await setup_test_org_job_and_candidate()

    async with async_session_factory() as session:
        candidates = await list_job_candidates_with_screening(
            session=session,
            job_id=env["job_id"],
            organization_id=env["org_id"],
        )

        assert len(candidates) == 1
        c = candidates[0]
        assert c.candidate_name == "Jane Doe"
        assert c.application_id == env["app_id"]
        assert c.has_resume is True


# 8. Tenant isolation on screening & shortlisting
@pytest.mark.asyncio
async def test_screening_tenant_isolation():
    env = await setup_test_org_job_and_candidate()
    other_org_id = uuid.uuid4()

    async with async_session_factory() as session:
        other_org = Organization(id=other_org_id, name="Other Org", slug=f"other-{uuid.uuid4().hex[:6]}")
        session.add(other_org)
        await session.commit()

    async with async_session_factory() as session:
        # Org B cannot view Org A screening report
        with pytest.raises(ApplicationNotFoundError):
            await build_candidate_screening_report(
                session=session,
                application_id=env["app_id"],
                organization_id=other_org_id,
            )

        # Org B cannot shortlist Org A candidate
        with pytest.raises(ApplicationNotFoundError):
            await apply_shortlist_decision(
                session=session,
                application_id=env["app_id"],
                organization_id=other_org_id,
                decision="SHORTLISTED",
            )


# 9. Real email-to-interview-ready pipeline with resume text & evidence extraction
@pytest.mark.asyncio
async def test_real_email_to_screening_pipeline():
    org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name="Pipeline Org", slug=f"pipe-{uuid.uuid4().hex[:6]}")
        session.add(org)
        await session.flush()

        user = User(
            id=user_id,
            organization_id=org_id,
            email=f"admin-{uuid.uuid4().hex[:6]}@pipe.test",
            password_hash="hash",
            full_name="Pipeline Admin",
            role="COMPANY_ADMIN",
        )
        session.add(user)
        await session.flush()

        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Senior Backend Engineer",
            description="FastAPI, PostgreSQL, Redis",
            status="PUBLISHED",
        )
        session.add(job)
        await session.flush()

        cap1 = Capability(id=uuid.uuid4(), job_id=job_id, name="FastAPI", description="FastAPI", importance="HIGH")
        cap2 = Capability(id=uuid.uuid4(), job_id=job_id, name="PostgreSQL", description="PostgreSQL", importance="HIGH")
        session.add_all([cap1, cap2])
        await session.commit()

    # Create mock normalized email arriving from Gmail with resume PDF
    incoming_email = NormalizedEmail(
        external_id="gmail-msg-12345",
        provider="GMAIL",
        sender_email="candidate.applicant@example.com",
        sender_name="Candidate Applicant",
        recipient_emails=["jobs@pipeline.com"],
        subject="Application for Senior Backend Engineer",
        body_text="Please find my resume attached for the Senior Backend Engineer opening.",
        received_at=datetime.utcnow() if "datetime" in globals() else __import__("datetime").datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="candidate_resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="gmail-att-01",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        # Run email intake
        intake_res = await process_email_intake(
            session=session,
            email=incoming_email,
            organization_id=org_id,
            target_job_id=job_id,
        )

        assert intake_res.classification == "CANDIDATE_APPLICATION"
        assert intake_res.intake_status == "PROCESSED"
        assert intake_res.should_process_resume is True
        assert intake_res.application_id is not None

        # Check application has extracted resume text and is in SCREENING
        app_obj = await session.get(Application, intake_res.application_id)
        assert app_obj.resume_text is not None
        assert "FastAPI" in app_obj.resume_text
        assert app_obj.status == "SCREENING"

        # Check screening report is generated
        screening_rep = await build_candidate_screening_report(
            session=session,
            application_id=intake_res.application_id,
            organization_id=org_id,
        )
        assert screening_rep.application_id == intake_res.application_id
        assert screening_rep.candidate_email == "candidate.applicant@example.com"
        assert len(screening_rep.requirements_evaluated) == 2


# 10. Idempotency across multiple syncs
@pytest.mark.asyncio
async def test_email_intake_idempotency_safe_resync():
    org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name="Resync Org", slug=f"resync-{uuid.uuid4().hex[:6]}")
        session.add(org)
        await session.flush()

        user = User(
            id=user_id,
            organization_id=org_id,
            email=f"hr-{uuid.uuid4().hex[:6]}@resync.test",
            password_hash="hash",
            full_name="Resync HR",
            role="COMPANY_ADMIN",
        )
        session.add(user)
        await session.flush()

        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Backend Lead",
            description="Lead engineer",
            status="PUBLISHED",
        )
        session.add(job)
        await session.commit()

    email_obj = NormalizedEmail(
        external_id="gmail-msg-resync-01",
        provider="GMAIL",
        sender_email="repeat.applicant@example.com",
        sender_name="Repeat Applicant",
        recipient_emails=["jobs@resync.com"],
        subject="Application for Backend Lead",
        body_text="Applying for the Backend Lead position.",
        received_at=__import__("datetime").datetime.utcnow(),
        attachments=[
            EmailAttachment(
                filename="repeat_resume.pdf",
                content_type="application/pdf",
                size=len(SAMPLE_RESUME_PDF_BYTES),
                provider_attachment_id="att-repeat",
                content=SAMPLE_RESUME_PDF_BYTES,
            )
        ],
    )

    async with async_session_factory() as session:
        # Sync 1
        res1 = await process_email_intake(
            session=session,
            email=email_obj,
            organization_id=org_id,
            target_job_id=job_id,
        )
        app_id_1 = res1.application_id
        cand_id_1 = res1.candidate_id

        # Sync 2 with exact same email
        res2 = await process_email_intake(
            session=session,
            email=email_obj,
            organization_id=org_id,
            target_job_id=job_id,
        )
        assert res2.application_id == app_id_1
        assert res2.candidate_id == cand_id_1
        assert res2.is_existing_application is True
        assert res2.is_existing_candidate is True
