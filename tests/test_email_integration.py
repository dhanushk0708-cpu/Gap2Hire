import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User
from app.schemas.email_integration import (
    AttachmentClassificationEnum,
    EmailClassificationEnum,
    EmailConnectionCreate,
)
from app.services.email_classifier import (
    classify_attachment,
    classify_email,
    find_primary_resume,
)
from app.services.email_connection import (
    EmailConnectionNotFoundError,
    create_email_connection,
    delete_email_connection,
    get_email_connection,
    list_email_connections,
)
from app.services.email_intake import process_email_intake
from app.services.email_provider import FakeEmailProvider


# 1. Fake provider returns exactly 10 deterministic emails
@pytest.mark.asyncio
async def test_fake_email_provider_returns_10_emails():
    provider = FakeEmailProvider(account_email="jobs@gap2hire.com")
    connected = await provider.connect({})
    assert connected is True

    emails = await provider.fetch_emails(limit=50)
    assert len(emails) == 10

    expected_ids = [f"fake-email-{i:02d}" for i in range(1, 11)]
    actual_ids = [e.external_id for e in emails]
    assert actual_ids == expected_ids

    # Verify get_email & get_attachment
    e1 = await provider.get_email("fake-email-01")
    assert e1 is not None
    assert e1.sender_email == "alice.smith@example.com"
    assert len(e1.attachments) == 1

    att_bytes = await provider.get_attachment("fake-email-01", "att-01-resume")
    assert att_bytes is not None
    assert att_bytes.startswith(b"%PDF")

    await provider.disconnect()


# 2. Candidate email classification (valid resume PDF)
@pytest.mark.asyncio
async def test_candidate_email_classification():
    provider = FakeEmailProvider()
    e1 = await provider.get_email("fake-email-01")
    e2 = await provider.get_email("fake-email-02")
    e4 = await provider.get_email("fake-email-04")

    cls1, _ = classify_email(e1)
    cls2, _ = classify_email(e2)
    cls4, _ = classify_email(e4)

    assert cls1 == EmailClassificationEnum.CANDIDATE_APPLICATION
    assert cls2 == EmailClassificationEnum.CANDIDATE_APPLICATION
    assert cls4 == EmailClassificationEnum.CANDIDATE_APPLICATION


# 3. Internal HR email classification
@pytest.mark.asyncio
async def test_internal_hr_classification():
    provider = FakeEmailProvider()
    e5 = await provider.get_email("fake-email-05")

    cls5, reason = classify_email(e5)
    assert cls5 == EmailClassificationEnum.IRRELEVANT
    assert "internal" in reason.lower() or "hr" in reason.lower()


# 4. Newsletter & Spam classification
@pytest.mark.asyncio
async def test_newsletter_and_spam_classification():
    provider = FakeEmailProvider()
    e6 = await provider.get_email("fake-email-06")
    e7 = await provider.get_email("fake-email-07")

    cls6, _ = classify_email(e6)
    cls7, _ = classify_email(e7)

    assert cls6 == EmailClassificationEnum.IRRELEVANT
    assert cls7 == EmailClassificationEnum.IRRELEVANT


# 5. Candidate with no attachment
@pytest.mark.asyncio
async def test_candidate_with_no_attachment():
    provider = FakeEmailProvider()
    e3 = await provider.get_email("fake-email-03")

    cls3, reason = classify_email(e3)
    assert cls3 == EmailClassificationEnum.POSSIBLE_APPLICATION
    assert "without resume attachment" in reason or "missing" in reason


# 6. Candidate with multiple attachments (inspect primary resume selection)
@pytest.mark.asyncio
async def test_multiple_attachments():
    provider = FakeEmailProvider()
    e8 = await provider.get_email("fake-email-08")
    assert len(e8.attachments) == 3

    primary_att, att_cls = find_primary_resume(e8.attachments)
    assert primary_att is not None
    assert primary_att.filename == "elena_rostova_resume.pdf"
    assert att_cls == AttachmentClassificationEnum.VALID_RESUME_PDF

    cls8, _ = classify_email(e8)
    assert cls8 == EmailClassificationEnum.CANDIDATE_APPLICATION


# 7. Candidate with invalid attachment (.exe)
@pytest.mark.asyncio
async def test_invalid_attachment():
    provider = FakeEmailProvider()
    e9 = await provider.get_email("fake-email-09")
    assert len(e9.attachments) == 1

    att_cls = classify_attachment(e9.attachments[0])
    assert att_cls == AttachmentClassificationEnum.INVALID_ATTACHMENT

    cls9, reason = classify_email(e9)
    assert cls9 == EmailClassificationEnum.POSSIBLE_APPLICATION
    assert "invalid" in reason.lower()


# 8. Unclear email
@pytest.mark.asyncio
async def test_unclear_email():
    provider = FakeEmailProvider()
    e10 = await provider.get_email("fake-email-10")

    cls10, _ = classify_email(e10)
    assert cls10 == EmailClassificationEnum.UNKNOWN


# 9. Candidate intake result and idempotency (no duplicate application creation)
@pytest.mark.asyncio
async def test_candidate_intake_result_and_idempotency():
    org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with async_session_factory() as session:
        # Seed test org, user, and job
        org = Organization(id=org_id, name="Intake Test Org", slug=f"intake-org-{uuid.uuid4().hex[:6]}")
        session.add(org)
        await session.flush()

        user = User(
            id=user_id,
            organization_id=org_id,
            email=f"hr-{uuid.uuid4().hex[:6]}@intake.test",
            password_hash="hash",
            full_name="HR Intake Tester",
            role="COMPANY_ADMIN",
        )
        session.add(user)
        await session.flush()

        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Senior Backend Engineer",
            description="FastAPI, PostgreSQL, AsyncIO",
            status="PUBLISHED",
        )
        session.add(job)
        await session.commit()

    provider = FakeEmailProvider()
    e1_raw = await provider.get_email("fake-email-01")
    unique_sender = f"alice-{uuid.uuid4().hex[:6]}@example.com"
    e1 = e1_raw.model_copy(update={"sender_email": unique_sender, "external_id": f"fake-{uuid.uuid4().hex[:6]}"})

    async with async_session_factory() as session:
        # First Intake Run -> Creates Candidate & Application
        res1 = await process_email_intake(
            session=session,
            email=e1,
            organization_id=org_id,
            target_job_id=job_id,
        )

        assert res1.classification == EmailClassificationEnum.CANDIDATE_APPLICATION
        assert res1.is_existing_candidate is False
        assert res1.is_existing_application is False
        assert res1.candidate_id is not None
        assert res1.application_id is not None
        assert res1.should_process_resume is True
        assert res1.intake_status == "PROCESSED"
        first_candidate_id = res1.candidate_id
        first_app_id = res1.application_id

        # Second Intake Run with same email -> Reuses Candidate & Application without duplicates
        res2 = await process_email_intake(
            session=session,
            email=e1,
            organization_id=org_id,
            target_job_id=job_id,
        )

        assert res2.is_existing_candidate is True
        assert res2.is_existing_application is True
        assert res2.candidate_id == first_candidate_id
        assert res2.application_id == first_app_id
        assert res2.should_process_resume is True


# 10. Tenant isolation verification
@pytest.mark.asyncio
async def test_tenant_isolation():
    org_a_id = uuid.uuid4()
    org_b_id = uuid.uuid4()

    async with async_session_factory() as session:
        org_a = Organization(id=org_a_id, name="Tenant A", slug=f"tenant-a-{uuid.uuid4().hex[:6]}")
        org_b = Organization(id=org_b_id, name="Tenant B", slug=f"tenant-b-{uuid.uuid4().hex[:6]}")
        session.add_all([org_a, org_b])
        await session.commit()

    async with async_session_factory() as session:
        # Org A creates connection
        conn_a = await create_email_connection(
            session=session,
            organization_id=org_a_id,
            data=EmailConnectionCreate(
                provider="FAKE",
                account_email="careers@tenanta.com",
            ),
        )
        assert conn_a.organization_id == org_a_id

        # Org A can list its connections
        conns_a = await list_email_connections(session=session, organization_id=org_a_id)
        assert len(conns_a) == 1
        assert conns_a[0].id == conn_a.id

        # Org B listing shows empty
        conns_b = await list_email_connections(session=session, organization_id=org_b_id)
        assert len(conns_b) == 0

        # Org B attempting to get Org A's connection raises EmailConnectionNotFoundError
        with pytest.raises(EmailConnectionNotFoundError):
            await get_email_connection(
                session=session,
                connection_id=conn_a.id,
                organization_id=org_b_id,
            )

        # Org B attempting to delete Org A's connection raises EmailConnectionNotFoundError
        with pytest.raises(EmailConnectionNotFoundError):
            await delete_email_connection(
                session=session,
                connection_id=conn_a.id,
                organization_id=org_b_id,
            )

        # Clean up Org A connection
        await delete_email_connection(
            session=session,
            connection_id=conn_a.id,
            organization_id=org_a_id,
        )
        conns_a_after = await list_email_connections(session=session, organization_id=org_a_id)
        assert len(conns_a_after) == 0
