import os
import re

from app.schemas.email_integration import (
    AttachmentClassificationEnum,
    EmailAttachment,
    EmailClassificationEnum,
    NormalizedEmail,
)

DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".vbs", ".js", ".msi", ".bin", ".com", ".scr", ".jar", ".ps1"
}

SPAM_KEYWORDS = [
    r"congratulations! claim",
    r"claim your",
    r"exclusive cash prize",
    r"win a",
    r"gift card",
    r"click the link immediately to claim",
    r"unsubscribe",
    r"newsletter",
    r"weekly digest",
    r"manage preferences or unsubscribe",
]

INTERNAL_KEYWORDS = [
    r"headcount",
    r"q3 hiring plan",
    r"quarterly budget review",
    r"all-hands",
    r"internal hiring targets",
    r"payroll",
]

APPLICATION_KEYWORDS = [
    r"application",
    r"applying for",
    r"open position",
    r"backend developer",
    r"senior backend engineer",
    r"backend role",
    r"backend specialist",
    r"resume",
    r"cv",
    r"hiring team",
    r"recruitment team",
    r"please find my resume",
    r"attached is my latest cv",
]


def classify_attachment(attachment: EmailAttachment) -> AttachmentClassificationEnum:
    """Classifies an individual email attachment by file extension and MIME type."""
    ext = os.path.splitext(attachment.filename.lower())[1]
    content_type = attachment.content_type.lower()

    if ext in DANGEROUS_EXTENSIONS or "msdownload" in content_type:
        return AttachmentClassificationEnum.INVALID_ATTACHMENT

    if ext == ".pdf" or content_type == "application/pdf":
        return AttachmentClassificationEnum.VALID_RESUME_PDF

    if ext in {".docx", ".doc"} or "wordprocessingml" in content_type or "msword" in content_type:
        return AttachmentClassificationEnum.POSSIBLE_RESUME_DOC

    return AttachmentClassificationEnum.OTHER_DOCUMENT


def find_primary_resume(
    attachments: list[EmailAttachment],
) -> tuple[EmailAttachment | None, AttachmentClassificationEnum]:
    """Identifies the primary resume attachment from a list of attachments."""
    if not attachments:
        return None, AttachmentClassificationEnum.OTHER_DOCUMENT

    classified = [(att, classify_attachment(att)) for att in attachments]

    # 1. Look for PDF with 'resume' or 'cv' in name
    for att, cls_type in classified:
        if cls_type == AttachmentClassificationEnum.VALID_RESUME_PDF:
            name_lower = att.filename.lower()
            if "resume" in name_lower or "cv" in name_lower:
                return att, cls_type

    # 2. Look for any valid PDF
    for att, cls_type in classified:
        if cls_type == AttachmentClassificationEnum.VALID_RESUME_PDF:
            return att, cls_type

    # 3. Look for docx/doc resume
    for att, cls_type in classified:
        if cls_type == AttachmentClassificationEnum.POSSIBLE_RESUME_DOC:
            return att, cls_type

    # 4. Check for invalid attachment if no valid resume
    for att, cls_type in classified:
        if cls_type == AttachmentClassificationEnum.INVALID_ATTACHMENT:
            return att, cls_type

    # 5. Default first attachment
    first_att, first_cls = classified[0]
    return first_att, first_cls


def classify_email(email: NormalizedEmail) -> tuple[EmailClassificationEnum, str]:
    """Deterministically classifies an email into CANDIDATE_APPLICATION, POSSIBLE_APPLICATION, IRRELEVANT, or UNKNOWN."""
    sender = email.sender_email.lower()
    subject = email.subject.lower()
    body = email.body_text.lower()
    combined_text = f"{subject}\n{body}"

    # 1. Spam & Newsletter check
    if sender.endswith(".spam") or any(kw in sender for kw in ["promotions@", "lottery@", "offers@", "digest@"]):
        return EmailClassificationEnum.IRRELEVANT, "Sender domain or address identified as promotional/spam."

    for pattern in SPAM_KEYWORDS:
        if re.search(pattern, combined_text):
            return EmailClassificationEnum.IRRELEVANT, f"Content matched marketing/spam pattern: {pattern}"

    # 2. Internal HR / Operations check
    if sender.endswith(".internal") or "hr-operations@" in sender or "hr-ops@" in sender:
        return EmailClassificationEnum.IRRELEVANT, "Internal company domain or HR operational sender."

    for pattern in INTERNAL_KEYWORDS:
        if re.search(pattern, combined_text):
            return EmailClassificationEnum.IRRELEVANT, f"Internal organizational subject pattern: {pattern}"

    # 3. Candidate Application intent check
    has_app_signals = False
    for pattern in APPLICATION_KEYWORDS:
        if re.search(pattern, combined_text):
            has_app_signals = True
            break

    if has_app_signals:
        primary_att, att_cls = find_primary_resume(email.attachments)

        if att_cls == AttachmentClassificationEnum.VALID_RESUME_PDF:
            return EmailClassificationEnum.CANDIDATE_APPLICATION, "Candidate application with valid resume PDF."

        if att_cls == AttachmentClassificationEnum.POSSIBLE_RESUME_DOC:
            return EmailClassificationEnum.CANDIDATE_APPLICATION, "Candidate application with Word document resume."

        if att_cls == AttachmentClassificationEnum.INVALID_ATTACHMENT:
            return EmailClassificationEnum.POSSIBLE_APPLICATION, "Application intent detected with invalid attachment format."

        if not email.attachments:
            return EmailClassificationEnum.POSSIBLE_APPLICATION, "Application intent detected without resume attachment."

        return EmailClassificationEnum.POSSIBLE_APPLICATION, "Application intent detected with non-resume attachment."

    # 4. Unknown / Unclear
    return EmailClassificationEnum.UNKNOWN, "No clear candidate application or operational signals detected."
