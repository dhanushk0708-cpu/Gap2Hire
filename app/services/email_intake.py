import json
import logging
import re
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.email_connection import EmailConnection
from app.models.imported_email import ImportedEmail
from app.models.job import Job
from app.models.organization import Organization
from app.schemas.email_integration import (
    AttachmentClassificationEnum,
    BatchEmailSyncResponse,
    EmailClassificationEnum,
    EmailIntakeResult,
    NormalizedEmail,
)
from app.services.email_classifier import classify_email, find_primary_resume
from app.services.email_provider import FakeEmailProvider

logger = logging.getLogger(__name__)


async def match_job_for_email(
    session: AsyncSession,
    organization_id: UUID,
    email: NormalizedEmail,
    explicit_job_id: UUID | None = None,
) -> Job | None:
    """Matches a job for the email from explicit ID or by searching job titles against email subject/body."""
    if explicit_job_id:
        stmt = select(Job).where(
            Job.id == explicit_job_id,
            Job.organization_id == organization_id,
        )
        return await session.scalar(stmt)

    # Search published/active jobs for this organization
    stmt = (
        select(Job)
        .where(
            Job.organization_id == organization_id,
            Job.status.in_(["PUBLISHED", "ACTIVE", "DRAFT"]),
        )
        .order_by(Job.created_at.desc())
    )
    jobs = list((await session.scalars(stmt)).all())
    if not jobs:
        return None

    combined_text = f"{email.subject} {email.body_text}".lower()

    # Exact or fuzzy title match
    for job in jobs:
        title_clean = job.title.lower()
        words = [w for w in re.split(r"\W+", title_clean) if len(w) > 2]
        if words and all(w in combined_text for w in words):
            return job

    # Partial match
    for job in jobs:
        if job.title.lower() in combined_text:
            return job

    # Fallback to the latest active job if only 1 exists
    if len(jobs) == 1:
        return jobs[0]

    return None


async def process_email_intake(
    session: AsyncSession,
    email: NormalizedEmail,
    organization_id: UUID,
    connection_id: UUID | None = None,
    target_job_id: UUID | None = None,
    auto_create_candidate: bool = True,
    auto_create_application: bool = True,
) -> EmailIntakeResult:
    """Processes a normalized email through classification, candidate intake, and application creation with Gap2Hire-level idempotency."""
    # Tenant verification
    org = await session.get(Organization, organization_id)
    if not org:
        raise ValueError(f"Organization {organization_id} not found or inaccessible")

    # 1. Idempotency Check via ImportedEmail table
    ext_stmt = select(ImportedEmail).where(
        ImportedEmail.organization_id == organization_id,
        ImportedEmail.external_message_id == email.external_id,
    )
    existing_imported = await session.scalar(ext_stmt)

    if existing_imported and existing_imported.status in ("PROCESSED", "SKIPPED", "FLAGGED_REVIEW"):
        primary_att, _ = find_primary_resume(email.attachments)
        classification = EmailClassificationEnum(existing_imported.classification) if existing_imported.classification in EmailClassificationEnum.__members__ else EmailClassificationEnum.UNKNOWN
        return EmailIntakeResult(
            email_id=email.external_id,
            classification=classification,
            confidence="HIGH",
            candidate_email=existing_imported.sender_email,
            candidate_name=existing_imported.sender_name,
            candidate_id=existing_imported.candidate_id,
            is_existing_candidate=existing_imported.candidate_id is not None,
            application_id=existing_imported.application_id,
            is_existing_application=existing_imported.application_id is not None,
            job_id=existing_imported.job_id,
            primary_attachment=primary_att,
            attachment_count=len(email.attachments),
            should_process_resume=False,
            intake_status="SKIPPED",
            reason=f"Email external ID '{email.external_id}' was already processed previously (Status: {existing_imported.status}).",
        )

    # Create or update ImportedEmail tracking record
    if not existing_imported:
        imported_email = ImportedEmail(
            organization_id=organization_id,
            email_connection_id=connection_id,
            external_message_id=email.external_id,
            provider=email.provider,
            sender_email=email.sender_email,
            sender_name=email.sender_name,
            subject=email.subject[:500] if email.subject else None,
            status="PROCESSING",
            received_at=email.received_at,
        )
        session.add(imported_email)
        await session.flush()
    else:
        imported_email = existing_imported
        imported_email.status = "PROCESSING"
        await session.flush()

    # 2. Classify email and attachments
    classification, reason = classify_email(email)
    primary_att, att_cls = find_primary_resume(email.attachments)
    imported_email.classification = classification.value

    if classification == EmailClassificationEnum.IRRELEVANT:
        imported_email.status = "SKIPPED"
        imported_email.processed_at = datetime.utcnow()
        await session.commit()
        return EmailIntakeResult(
            email_id=email.external_id,
            classification=classification,
            confidence="HIGH",
            candidate_email=email.sender_email,
            candidate_name=email.sender_name,
            attachment_count=len(email.attachments),
            primary_attachment=primary_att,
            should_process_resume=False,
            intake_status="IGNORED",
            reason=reason,
        )

    if classification == EmailClassificationEnum.UNKNOWN:
        imported_email.status = "SKIPPED"
        imported_email.processed_at = datetime.utcnow()
        await session.commit()
        return EmailIntakeResult(
            email_id=email.external_id,
            classification=classification,
            confidence="LOW",
            candidate_email=email.sender_email,
            candidate_name=email.sender_name,
            attachment_count=len(email.attachments),
            primary_attachment=primary_att,
            should_process_resume=False,
            intake_status="IGNORED",
            reason=reason,
        )

    if classification == EmailClassificationEnum.POSSIBLE_APPLICATION:
        imported_email.status = "FLAGGED_REVIEW"
        imported_email.processed_at = datetime.utcnow()
        await session.commit()
        return EmailIntakeResult(
            email_id=email.external_id,
            classification=classification,
            confidence="MEDIUM",
            candidate_email=email.sender_email,
            candidate_name=email.sender_name,
            attachment_count=len(email.attachments),
            primary_attachment=primary_att,
            should_process_resume=False,
            intake_status="FLAGGED_REVIEW",
            reason=reason,
        )

    # 3. CANDIDATE_APPLICATION Intake
    cand_email = email.sender_email.strip().lower()
    cand_name = email.sender_name.strip() or "Candidate"

    # Candidate Lookup / Create
    cand_stmt = select(Candidate).where(Candidate.email == cand_email)
    candidate = await session.scalar(cand_stmt)
    is_existing_candidate = False

    if candidate:
        is_existing_candidate = True
    elif auto_create_candidate:
        candidate = Candidate(
            full_name=cand_name,
            email=cand_email,
        )
        session.add(candidate)
        await session.flush()

    # Job Resolution
    matched_job = await match_job_for_email(
        session=session,
        organization_id=organization_id,
        email=email,
        explicit_job_id=target_job_id,
    )

    application_id = None
    is_existing_application = False

    if not matched_job:
        # Ambiguous job target -> flag for manual HR assignment
        imported_email.status = "FLAGGED_REVIEW"
        imported_email.candidate_id = candidate.id if candidate else None
        imported_email.error_message = "Ambiguous job target. Marked for HR manual job assignment."
        imported_email.processed_at = datetime.utcnow()
        await session.commit()

        return EmailIntakeResult(
            email_id=email.external_id,
            classification=classification,
            confidence="MEDIUM",
            candidate_email=cand_email,
            candidate_name=cand_name,
            candidate_id=candidate.id if candidate else None,
            is_existing_candidate=is_existing_candidate,
            application_id=None,
            is_existing_application=False,
            job_id=None,
            job_title_detected=None,
            primary_attachment=primary_att,
            attachment_count=len(email.attachments),
            should_process_resume=False,
            intake_status="FLAGGED_REVIEW",
            reason="Ambiguous job target. Marked for HR manual job assignment.",
        )

    if candidate and matched_job:
        # Check for existing application
        app_stmt = select(Application).where(
            Application.candidate_id == candidate.id,
            Application.job_id == matched_job.id,
        )
        existing_app = await session.scalar(app_stmt)

        if existing_app:
            is_existing_application = True
            application_id = existing_app.id
            target_app = existing_app
        elif auto_create_application:
            new_app = Application(
                candidate_id=candidate.id,
                job_id=matched_job.id,
                status="APPLIED",
            )
            session.add(new_app)
            await session.flush()
            application_id = new_app.id
            target_app = new_app
        else:
            target_app = None

        # Resume text extraction, Evidence analysis, & Preliminary Screening
        if target_app and primary_att and primary_att.content and att_cls == AttachmentClassificationEnum.VALID_RESUME_PDF:
            try:
                from app.services.evidence import analyze_application_evidence
                from app.services.resume_processor import extract_text_from_pdf_bytes
                from app.services.screening import build_candidate_screening_report

                resume_text = extract_text_from_pdf_bytes(primary_att.content)
                target_app.resume_text = resume_text
                target_app.resume_path = f"resumes/{target_app.id}_{primary_att.filename}"
                target_app.status = "SCREENING"
                await session.flush()

                # Sync candidate sources discovered in resume text
                try:
                    from app.services.resume_url_discovery import sync_resume_candidate_sources
                    await sync_resume_candidate_sources(
                        session=session,
                        organization_id=organization_id,
                        application_id=target_app.id,
                        resume_text=resume_text,
                    )
                except Exception as src_err:
                    logger.info(f"Candidate source discovery notice during intake: {src_err}")

                # Extract resume evidence for capabilities
                try:
                    await analyze_application_evidence(
                        session=session,
                        application_id=target_app.id,
                        organization_id=organization_id,
                    )
                except Exception as ev_err:
                    logger.info(f"Evidence extraction notice during intake: {ev_err}")

                # Build preliminary screening evaluation
                try:
                    screening_rep = await build_candidate_screening_report(
                        session=session,
                        application_id=target_app.id,
                        organization_id=organization_id,
                    )
                    target_app.screening_status = screening_rep.screening_status
                except Exception as scr_err:
                    logger.info(f"Screening report notice during intake: {scr_err}")

            except Exception as resume_err:
                logger.warning(f"Could not parse resume attachment {primary_att.filename}: {resume_err}")

    imported_email.status = "PROCESSED"
    imported_email.job_id = matched_job.id if matched_job else None
    imported_email.candidate_id = candidate.id if candidate else None
    imported_email.application_id = application_id
    imported_email.resumes_count = 1 if (primary_att and att_cls == AttachmentClassificationEnum.VALID_RESUME_PDF) else 0
    imported_email.processed_at = datetime.utcnow()

    await session.commit()

    should_process_resume = bool(
        att_cls == AttachmentClassificationEnum.VALID_RESUME_PDF
        and application_id is not None
    )

    return EmailIntakeResult(
        email_id=email.external_id,
        classification=classification,
        confidence="HIGH",
        candidate_email=cand_email,
        candidate_name=cand_name,
        candidate_id=candidate.id if candidate else None,
        is_existing_candidate=is_existing_candidate,
        application_id=application_id,
        is_existing_application=is_existing_application,
        job_id=matched_job.id if matched_job else None,
        job_title_detected=matched_job.title if matched_job else None,
        primary_attachment=primary_att,
        attachment_count=len(email.attachments),
        should_process_resume=should_process_resume,
        intake_status="PROCESSED",
        reason=reason,
    )


async def batch_sync_emails(
    session: AsyncSession,
    organization_id: UUID,
    connection_id: UUID | None = None,
    limit: int = 10,
    target_job_id: UUID | None = None,
) -> BatchEmailSyncResponse:
    """Executes a bounded batch sync (LOAD NEW RESUMES) from the email provider with full idempotency and aggregation."""
    # Tenant verification
    org = await session.get(Organization, organization_id)
    if not org:
        raise ValueError(f"Organization {organization_id} not found or inaccessible")

    # Resolve email connection
    conn = None
    if connection_id:
        stmt = select(EmailConnection).where(
            EmailConnection.id == connection_id,
            EmailConnection.organization_id == organization_id,
        )
        conn = await session.scalar(stmt)
    else:
        # Fallback to active organization connection
        stmt = (
            select(EmailConnection)
            .where(
                EmailConnection.organization_id == organization_id,
                EmailConnection.status == "ACTIVE",
            )
            .order_by(EmailConnection.created_at.desc())
        )
        conn = await session.scalar(stmt)

    # Instantiate provider
    if conn and conn.provider.upper() == "GMAIL":
        from app.services.gmail_provider import GmailProvider

        auth_data = {}
        if conn.auth_payload_encrypted:
            try:
                auth_data = json.loads(conn.auth_payload_encrypted)
            except Exception:
                pass
        provider = GmailProvider(
            access_token=auth_data.get("access_token", ""),
            account_email=conn.account_email,
        )
    else:
        account_email = conn.account_email if conn else f"jobs@{org.slug or 'gap2hire'}.com"
        provider = FakeEmailProvider(account_email=account_email)

    # Fetch bounded batch of emails
    emails = await provider.fetch_emails(limit=limit)
    if not isinstance(emails, list):
        emails = []

    response = BatchEmailSyncResponse(
        emails_fetched=len(emails),
    )

    for em in emails:
        try:
            intake_res = await process_email_intake(
                session=session,
                email=em,
                organization_id=organization_id,
                connection_id=conn.id if conn else None,
                target_job_id=target_job_id,
            )
            response.details.append(intake_res)

            if intake_res.intake_status == "SKIPPED":
                response.duplicates_skipped += 1
            elif intake_res.classification == EmailClassificationEnum.CANDIDATE_APPLICATION:
                response.candidate_emails += 1
                if intake_res.primary_attachment:
                    response.resumes_found += 1
                if intake_res.should_process_resume:
                    response.resumes_processed += 1
            elif intake_res.classification == EmailClassificationEnum.IRRELEVANT:
                response.irrelevant_emails += 1
            elif intake_res.classification == EmailClassificationEnum.POSSIBLE_APPLICATION:
                response.possible_applications += 1

        except Exception as item_err:
            logger.error(f"Error processing email {em.external_id}: {item_err}", exc_info=True)
            response.failures += 1

    return response
