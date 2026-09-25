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
        assert res2.should_process_resume is False
        assert res2.intake_status == "SKIPPED"


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


# 11. Google OAuth Redirect URI Mismatch Fix Verification
def test_google_oauth_canonical_redirect_uri():
    import urllib.parse
    from app.services.gmail_provider import get_google_auth_url, get_google_redirect_uri

    redirect_uri = get_google_redirect_uri()
    expected_canonical_uri = "http://localhost:8000/api/v1/email-connections/oauth/callback"
    assert redirect_uri == expected_canonical_uri

    auth_url = get_google_auth_url(state="test-org-123")
    parsed_url = urllib.parse.urlparse(auth_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    assert "redirect_uri" in query_params
    assert query_params["redirect_uri"][0] == expected_canonical_uri


def test_fastapi_callback_route_exists():
    from app.main import app

    paths = list(app.openapi()["paths"].keys())
    expected_callback_path = "/api/v1/email-connections/oauth/callback"
    assert expected_callback_path in paths, f"Expected route {expected_callback_path} not found in FastAPI OpenAPI schema paths: {paths}"


# 12. Gmail message parsing with RFC 2047 MIME headers and UTF-8 text
def test_gmail_message_parsing_utf8_and_mime_headers():
    from app.services.gmail_provider import decode_mime_header, decode_text_bytes, clean_html_to_text

    # RFC 2047 encoded header
    encoded_subject = "=?UTF-8?B?QXBwbGljYXRpb24gZm9yIFNlbmlvciBFbmdpbmVlcg==?="
    assert decode_mime_header(encoded_subject) == "Application for Senior Engineer"

    # HTML to text clean
    html_sample = "<p>Dear Hiring Team,<br>Please find my resume attached.</p>"
    cleaned = clean_html_to_text(html_sample)
    assert "Dear Hiring Team," in cleaned
    assert "Please find my resume attached." in cleaned


# 13. Gmail message containing non-UTF-8 / ISO-8859-1 text
def test_gmail_message_non_utf8_charset():
    from app.services.gmail_provider import decode_text_bytes

    # ISO-8859-1 encoded string with accented character (e.g., José)
    latin1_bytes = "Resume of José Müller".encode("iso-8859-1")
    decoded = decode_text_bytes(latin1_bytes, charset="iso-8859-1")
    assert "José Müller" in decoded

    # Malformed bytes fallback
    malformed_bytes = b"Test malformed \xff\xfe bytes"
    decoded_fallback = decode_text_bytes(malformed_bytes, charset="utf-8")
    assert "Test malformed" in decoded_fallback


# 14. Gmail message with binary PDF attachment
def test_gmail_message_with_binary_pdf_attachment():
    import base64
    from app.schemas.email_integration import EmailAttachment
    from app.services.gmail_provider import safe_b64url_decode

    binary_pdf = b"%PDF-1.4\n\xff\xfe\xfd\xfc binary content stream"
    b64_data = base64.urlsafe_b64encode(binary_pdf).decode("ascii")

    decoded_bytes = safe_b64url_decode(b64_data)
    assert decoded_bytes == binary_pdf

    att = EmailAttachment(
        filename="candidate_resume.pdf",
        content_type="application/pdf",
        size=len(binary_pdf),
        provider_attachment_id="att-pdf-01",
        content=binary_pdf,
    )
    # Binary bytes are preserved in memory
    assert att.content == binary_pdf


# 15. Gmail message with multiple attachments
def test_gmail_message_with_multiple_attachments():
    from app.schemas.email_integration import EmailAttachment
    from app.services.email_classifier import find_primary_resume

    pdf_att = EmailAttachment(
        filename="resume.pdf",
        content_type="application/pdf",
        size=1024,
        provider_attachment_id="att-1",
        content=b"%PDF-1.4\n\x80\x81 binary resume",
    )
    img_att = EmailAttachment(
        filename="portfolio.png",
        content_type="image/png",
        size=2048,
        provider_attachment_id="att-2",
        content=b"\x89PNG\r\n\x1a\n binary image",
    )

    primary, cls = find_primary_resume([img_att, pdf_att])
    assert primary is not None
    assert primary.filename == "resume.pdf"


# 16. Batch sync response JSON serialization with binary data (Pydantic safety)
def test_batch_sync_response_json_serialization_with_binary_data():
    import json
    from app.schemas.email_integration import (
        BatchEmailSyncResponse,
        EmailAttachment,
        EmailClassificationEnum,
        EmailIntakeResult,
    )

    binary_pdf = b"%PDF-1.4\n\xed\xf2\x90\xaa arbitrary binary non-utf8 data"
    att = EmailAttachment(
        filename="resume.pdf",
        content_type="application/pdf",
        size=len(binary_pdf),
        provider_attachment_id="att-real-01",
        content=binary_pdf,
    )

    result = EmailIntakeResult(
        email_id="gmail-msg-12345",
        classification=EmailClassificationEnum.CANDIDATE_APPLICATION,
        confidence="HIGH",
        candidate_email="applicant@example.com",
        candidate_name="Jane Applicant",
        primary_attachment=att,
        attachment_count=1,
        should_process_resume=True,
        intake_status="PROCESSED",
        reason="Valid resume found",
    )

    batch_response = BatchEmailSyncResponse(
        emails_fetched=1,
        candidate_emails=1,
        resumes_found=1,
        resumes_processed=1,
        details=[result],
    )

    # Must serialize to valid JSON without PydanticSerializationError
    json_str = batch_response.model_dump_json()
    assert json_str is not None
    parsed = json.loads(json_str)
    assert parsed["emails_fetched"] == 1
    assert parsed["details"][0]["candidate_name"] == "Jane Applicant"
    assert parsed["details"][0]["primary_attachment"]["filename"] == "resume.pdf"
    # Ensure binary content was not serialized into JSON
    assert "content" not in parsed["details"][0]["primary_attachment"]

