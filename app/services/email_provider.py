from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.schemas.email_integration import EmailAttachment, NormalizedEmail

SAMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 712 Td (Candidate Resume) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n0000000201 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n296\n%%EOF"


class EmailProvider(ABC):
    """Abstract Base Class for all Email Ingestion Providers (Fake, Gmail, Microsoft 365, etc.)."""

    @abstractmethod
    async def connect(self, connection_data: dict[str, Any]) -> bool:
        """Establishes authenticated connection or session with the email provider."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnects or closes session with the email provider."""
        pass

    @abstractmethod
    async def fetch_emails(
        self,
        limit: int = 50,
        query: str | None = None,
    ) -> list[NormalizedEmail]:
        """Fetches normalized emails from the inbox matching query/limit."""
        pass

    @abstractmethod
    async def get_email(self, external_id: str) -> NormalizedEmail | None:
        """Fetches a single normalized email by its provider external id."""
        pass

    @abstractmethod
    async def get_attachment(
        self,
        external_id: str,
        attachment_id: str,
    ) -> bytes | None:
        """Fetches binary payload of an attachment by provider reference."""
        pass


class FakeEmailProvider(EmailProvider):
    """Deterministic synthetic email provider returning exactly 10 representative test emails."""

    def __init__(self, account_email: str = "careers@company.example"):
        self.account_email = account_email
        self.connected = False
        self._emails: list[NormalizedEmail] = self._build_synthetic_dataset()

    def _build_synthetic_dataset(self) -> list[NormalizedEmail]:
        base_time = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)

        return [
            # 1. Candidate application + resume PDF
            NormalizedEmail(
                external_id="fake-email-01",
                provider="FAKE",
                sender_email="alice.smith@example.com",
                sender_name="Alice Smith",
                recipient_emails=[self.account_email],
                subject="Application for Senior Backend Engineer",
                body_text=(
                    "Dear Hiring Team,\n\n"
                    "I am excited to submit my application for the Senior Backend Engineer role. "
                    "I have 5+ years of experience in Python, FastAPI, and scalable system design.\n"
                    "Please find my resume attached.\n\n"
                    "Best regards,\nAlice Smith"
                ),
                received_at=base_time,
                attachments=[
                    EmailAttachment(
                        filename="alice_smith_resume.pdf",
                        content_type="application/pdf",
                        size=len(SAMPLE_PDF_BYTES),
                        provider_attachment_id="att-01-resume",
                        content=SAMPLE_PDF_BYTES,
                    )
                ],
                metadata={"test_case": "candidate_with_valid_resume_1"},
            ),

            # 2. Candidate application + resume PDF
            NormalizedEmail(
                external_id="fake-email-02",
                provider="FAKE",
                sender_email="bob.jones@example.com",
                sender_name="Bob Jones",
                recipient_emails=[self.account_email],
                subject="Applying for Backend Developer role",
                body_text=(
                    "Hello Recruitment Team,\n\n"
                    "I would love to be considered for the open Backend Developer position at Gap2Hire. "
                    "Attached is my latest CV highlighting my distributed systems background.\n\n"
                    "Thanks,\nBob Jones"
                ),
                received_at=base_time,
                attachments=[
                    EmailAttachment(
                        filename="bob_jones_cv.pdf",
                        content_type="application/pdf",
                        size=len(SAMPLE_PDF_BYTES),
                        provider_attachment_id="att-02-cv",
                        content=SAMPLE_PDF_BYTES,
                    )
                ],
                metadata={"test_case": "candidate_with_valid_resume_2"},
            ),

            # 3. Candidate application with no attachment
            NormalizedEmail(
                external_id="fake-email-03",
                provider="FAKE",
                sender_email="charlie.brown@example.com",
                sender_name="Charlie Brown",
                recipient_emails=[self.account_email],
                subject="Application for Backend Role - Charlie Brown",
                body_text=(
                    "Hi,\n\n"
                    "I am writing to express my interest in the Backend Engineer opening. "
                    "I will forward my CV separately in a follow-up email shortly.\n\n"
                    "Best,\nCharlie Brown"
                ),
                received_at=base_time,
                attachments=[],
                metadata={"test_case": "candidate_no_attachment"},
            ),

            # 4. Existing candidate + resume
            NormalizedEmail(
                external_id="fake-email-04",
                provider="FAKE",
                sender_email="diana.prince@example.com",
                sender_name="Diana Prince",
                recipient_emails=[self.account_email],
                subject="Updated CV for Senior Backend Engineer",
                body_text=(
                    "Hi Gap2Hire Team,\n\n"
                    "Following up on my profile for the Senior Backend Engineer position, "
                    "please find my updated resume attached with my latest certifications.\n\n"
                    "Diana Prince"
                ),
                received_at=base_time,
                attachments=[
                    EmailAttachment(
                        filename="diana_prince_resume_v2.pdf",
                        content_type="application/pdf",
                        size=len(SAMPLE_PDF_BYTES),
                        provider_attachment_id="att-04-updated-resume",
                        content=SAMPLE_PDF_BYTES,
                    )
                ],
                metadata={"test_case": "existing_candidate_updated_resume"},
            ),

            # 5. Internal HR email
            NormalizedEmail(
                external_id="fake-email-05",
                provider="FAKE",
                sender_email="hr-operations@company.internal",
                sender_name="HR Operations",
                recipient_emails=[self.account_email, "lead@company.internal"],
                subject="Q3 Hiring Plan & Headcount Review",
                body_text=(
                    "Hi All,\n\n"
                    "Attached is the headcount budget and interview schedule for next quarter's engineering hiring.\n"
                    "Please review before Monday's sync.\n\n"
                    "Regards,\nHR Ops"
                ),
                received_at=base_time,
                attachments=[],
                metadata={"test_case": "internal_hr_email"},
            ),

            # 6. Newsletter
            NormalizedEmail(
                external_id="fake-email-06",
                provider="FAKE",
                sender_email="weekly-digest@techtrends.example",
                sender_name="Tech Trends Weekly",
                recipient_emails=[self.account_email],
                subject="Tech Trends Weekly: Distributed Systems Architecture",
                body_text=(
                    "Welcome to this week's newsletter covering microservices resilience, "
                    "event streaming, and database scaling.\n\n"
                    "To manage preferences or unsubscribe, click here."
                ),
                received_at=base_time,
                attachments=[],
                metadata={"test_case": "newsletter"},
            ),

            # 7. Spam-like email
            NormalizedEmail(
                external_id="fake-email-07",
                provider="FAKE",
                sender_email="promotions@instant-prizes.spam",
                sender_name="Special Promotions",
                recipient_emails=[self.account_email],
                subject="CONGRATULATIONS! Claim your $1000 prize now!",
                body_text=(
                    "Dear Winner,\n\n"
                    "You have been selected for an exclusive reward voucher! "
                    "Click the link immediately to claim your cash gift card!\n"
                    "Offer expires in 2 hours."
                ),
                received_at=base_time,
                attachments=[],
                metadata={"test_case": "spam"},
            ),

            # 8. Candidate application + multiple attachments
            NormalizedEmail(
                external_id="fake-email-08",
                provider="FAKE",
                sender_email="elena.rostova@example.com",
                sender_name="Elena Rostova",
                recipient_emails=[self.account_email],
                subject="Application: Senior Backend Engineer - Elena Rostova",
                body_text=(
                    "Dear Hiring Team,\n\n"
                    "Please find attached my resume, cover letter, and system architecture portfolio "
                    "for the Senior Backend Engineer role.\n\n"
                    "Sincerely,\nElena Rostova"
                ),
                received_at=base_time,
                attachments=[
                    EmailAttachment(
                        filename="elena_rostova_resume.pdf",
                        content_type="application/pdf",
                        size=len(SAMPLE_PDF_BYTES),
                        provider_attachment_id="att-08-resume",
                        content=SAMPLE_PDF_BYTES,
                    ),
                    EmailAttachment(
                        filename="cover_letter.pdf",
                        content_type="application/pdf",
                        size=len(SAMPLE_PDF_BYTES),
                        provider_attachment_id="att-08-cover",
                        content=SAMPLE_PDF_BYTES,
                    ),
                    EmailAttachment(
                        filename="portfolio_projects.zip",
                        content_type="application/zip",
                        size=1024,
                        provider_attachment_id="att-08-zip",
                        content=b"PK\x03\x04fake_zip_bytes",
                    ),
                ],
                metadata={"test_case": "candidate_multiple_attachments"},
            ),

            # 9. Candidate application + invalid attachment
            NormalizedEmail(
                external_id="fake-email-09",
                provider="FAKE",
                sender_email="frank.castle@example.com",
                sender_name="Frank Castle",
                recipient_emails=[self.account_email],
                subject="Job Application: Backend Specialist",
                body_text=(
                    "Hello,\n\n"
                    "I am applying for the backend role. Please launch the attached application to view my portfolio.\n\n"
                    "Frank Castle"
                ),
                received_at=base_time,
                attachments=[
                    EmailAttachment(
                        filename="portfolio_setup.exe",
                        content_type="application/x-msdownload",
                        size=2048,
                        provider_attachment_id="att-09-exe",
                        content=b"MZ\x90\x00fake_executable_binary",
                    )
                ],
                metadata={"test_case": "candidate_invalid_attachment"},
            ),

            # 10. Unclear email
            NormalizedEmail(
                external_id="fake-email-10",
                provider="FAKE",
                sender_email="sam.mystery@randomdomain.org",
                sender_name="Sam Mystery",
                recipient_emails=[self.account_email],
                subject="Check out this document",
                body_text=(
                    "Hey,\n\n"
                    "Here are some notes from our previous call regarding the system notes.\n\n"
                    "Sam"
                ),
                received_at=base_time,
                attachments=[
                    EmailAttachment(
                        filename="meeting_notes.txt",
                        content_type="text/plain",
                        size=32,
                        provider_attachment_id="att-10-txt",
                        content=b"Notes from meeting on Wednesday",
                    )
                ],
                metadata={"test_case": "unclear_email"},
            ),
        ]

    async def connect(self, connection_data: dict[str, Any]) -> bool:
        self.connected = True
        return True

    async def disconnect(self) -> bool:
        self.connected = False
        return True

    async def fetch_emails(
        self,
        limit: int = 50,
        query: str | None = None,
    ) -> list[NormalizedEmail]:
        emails = self._emails
        if query:
            q = query.lower()
            emails = [
                e for e in emails
                if q in e.subject.lower() or q in e.body_text.lower() or q in e.sender_email.lower()
            ]
        return emails[:limit]

    async def get_email(self, external_id: str) -> NormalizedEmail | None:
        for e in self._emails:
            if e.external_id == external_id:
                return e
        return None

    async def get_attachment(
        self,
        external_id: str,
        attachment_id: str,
    ) -> bytes | None:
        email = await self.get_email(external_id)
        if not email:
            return None
        for att in email.attachments:
            if att.provider_attachment_id == attachment_id:
                return att.content
        return None
