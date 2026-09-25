from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmailClassificationEnum(str, Enum):
    CANDIDATE_APPLICATION = "CANDIDATE_APPLICATION"
    POSSIBLE_APPLICATION = "POSSIBLE_APPLICATION"
    IRRELEVANT = "IRRELEVANT"
    UNKNOWN = "UNKNOWN"


class AttachmentClassificationEnum(str, Enum):
    VALID_RESUME_PDF = "VALID_RESUME_PDF"
    POSSIBLE_RESUME_DOC = "POSSIBLE_RESUME_DOC"
    INVALID_ATTACHMENT = "INVALID_ATTACHMENT"
    OTHER_DOCUMENT = "OTHER_DOCUMENT"


class EmailAttachment(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    size: int = 0
    provider_attachment_id: str
    content: bytes | None = Field(default=None, exclude=True)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedEmail(BaseModel):
    external_id: str
    provider: str
    sender_email: str
    sender_name: str
    recipient_emails: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    received_at: datetime
    attachments: list[EmailAttachment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmailConnectionCreate(BaseModel):
    provider: str = "FAKE"
    account_email: str
    status: str = "ACTIVE"
    auth_payload_encrypted: str | None = None


class EmailConnectionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    provider: str
    account_email: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailProcessingStatusEnum(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    SKIPPED = "SKIPPED"
    FLAGGED_REVIEW = "FLAGGED_REVIEW"
    FAILED = "FAILED"


class EmailIntakeResult(BaseModel):
    email_id: str
    classification: EmailClassificationEnum
    confidence: str = "HIGH"
    candidate_email: str | None = None
    candidate_name: str | None = None
    candidate_id: UUID | None = None
    is_existing_candidate: bool = False
    application_id: UUID | None = None
    is_existing_application: bool = False
    job_id: UUID | None = None
    job_title_detected: str | None = None
    primary_attachment: EmailAttachment | None = None
    attachment_count: int = 0
    should_process_resume: bool = False
    intake_status: str = "IGNORED"
    reason: str = ""


class BatchEmailSyncResponse(BaseModel):
    emails_fetched: int = 0
    candidate_emails: int = 0
    irrelevant_emails: int = 0
    possible_applications: int = 0
    resumes_found: int = 0
    resumes_processed: int = 0
    duplicates_skipped: int = 0
    failures: int = 0
    details: list[EmailIntakeResult] = Field(default_factory=list)

