from datetime import datetime, timedelta
import hashlib
import logging
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.simulated_notification import SimulatedNotification

logger = logging.getLogger(__name__)

DEMO_DISCLAIMER_HEADER = (
    "===========================================================\n"
    "[DEMO MODE — EMAILS NOT SENT]\n"
    "This notification was generated in the Gap2Hire Demonstration\n"
    "Environment. No live emails or calendar invitations were dispatched.\n"
    "===========================================================\n\n"
)


def build_idempotency_key(
    interview_reference: str,
    notification_type: str,
    recipient: str,
    timestamp_bucket: Optional[str] = None,
) -> str:
    """Generates an idempotency key to prevent accidental duplicate dispatch."""
    raw = f"{interview_reference}:{notification_type}:{recipient}:{timestamp_bucket or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def format_invitation_notification(
    candidate_name: str,
    job_title: str,
    organization_name: str,
    scheduled_start: datetime,
    duration_minutes: int,
    timezone_name: str,
    interview_reference: str,
    interview_type: str = "ONLINE",
    meeting_url: Optional[str] = None,
    location: Optional[str] = None,
    interviewer_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> tuple[str, str]:
    """Formats interview invitation email subject and body."""
    date_str = scheduled_start.strftime("%A, %B %d, %Y")
    time_str = scheduled_start.strftime("%I:%M %p")
    end_time = scheduled_start + timedelta(minutes=duration_minutes)
    end_time_str = end_time.strftime("%I:%M %p")

    subject = f"Interview Invitation ({interview_reference}): {job_title} at {organization_name}"

    body = DEMO_DISCLAIMER_HEADER
    body += f"Dear {candidate_name},\n\n"
    body += f"You have been invited to an interview for the {job_title} role at {organization_name}.\n\n"
    body += "--- INTERVIEW DETAILS ---\n"
    body += f"• Reference: {interview_reference}\n"
    body += f"• Date: {date_str}\n"
    body += f"• Time: {time_str} - {end_time_str} ({timezone_name})\n"
    body += f"• Duration: {duration_minutes} minutes\n"
    body += f"• Format: {interview_type}\n"
    if interviewer_name:
        body += f"• Interviewer: {interviewer_name}\n"

    if interview_type.upper() == "ONLINE":
        body += f"• Demo Meeting Room: {meeting_url or 'N/A'}\n"
        body += "  (Note: Demonstration virtual room link for pairing/interview sandbox)\n"
    else:
        body += f"• In-Person Location: {location or 'Office Headquarters'}\n"

    if notes:
        body += f"\n--- INSTRUCTIONS & PREPARATION ---\n{notes}\n"

    body += (
        "\n--- JOINING INSTRUCTIONS ---\n"
        "1. Please test your setup 5 minutes before scheduled start.\n"
        "2. Ensure you have your workspace ready for technical review.\n\n"
        f"Warm regards,\n"
        f"Talent Acquisition Team\n"
        f"{organization_name}\n"
    )
    return subject, body


def format_rescheduled_notification(
    candidate_name: str,
    job_title: str,
    organization_name: str,
    new_start: datetime,
    duration_minutes: int,
    timezone_name: str,
    interview_reference: str,
    interview_type: str = "ONLINE",
    meeting_url: Optional[str] = None,
    location: Optional[str] = None,
    reason: Optional[str] = None,
) -> tuple[str, str]:
    """Formats reschedule email subject and body."""
    date_str = new_start.strftime("%A, %B %d, %Y")
    time_str = new_start.strftime("%I:%M %p")
    end_time = new_start + timedelta(minutes=duration_minutes)
    end_time_str = end_time.strftime("%I:%M %p")

    subject = f"Interview Rescheduled ({interview_reference}): {job_title} at {organization_name}"

    body = DEMO_DISCLAIMER_HEADER
    body += f"Dear {candidate_name},\n\n"
    body += f"Your interview for {job_title} at {organization_name} has been rescheduled to a new time slot.\n\n"
    body += "--- UPDATED INTERVIEW SCHEDULE ---\n"
    body += f"• Reference: {interview_reference}\n"
    body += f"• New Date: {date_str}\n"
    body += f"• New Time: {time_str} - {end_time_str} ({timezone_name})\n"
    body += f"• Duration: {duration_minutes} minutes\n"

    if interview_type.upper() == "ONLINE" and meeting_url:
        body += f"• Demo Meeting Room: {meeting_url}\n"
    elif location:
        body += f"• Location: {location}\n"

    if reason:
        body += f"\n• Reason for Change: {reason}\n"

    body += (
        "\nPlease update your calendar accordingly. If you have any questions, feel free to reply.\n\n"
        f"Best regards,\n"
        f"{organization_name} Hiring Team\n"
    )
    return subject, body


def format_cancelled_notification(
    candidate_name: str,
    job_title: str,
    organization_name: str,
    interview_reference: str,
    cancellation_reason: Optional[str] = None,
) -> tuple[str, str]:
    """Formats cancellation email subject and body."""
    subject = f"Interview Cancelled ({interview_reference}): {job_title} at {organization_name}"

    body = DEMO_DISCLAIMER_HEADER
    body += f"Dear {candidate_name},\n\n"
    body += f"Please be advised that your upcoming interview ({interview_reference}) for {job_title} at {organization_name} has been cancelled.\n\n"
    if cancellation_reason:
        body += f"Reason provided: {cancellation_reason}\n\n"
    body += (
        "Our recruiting team will contact you if alternate arrangements or future openings arise.\n\n"
        f"Best regards,\n"
        f"Hiring Operations\n"
        f"{organization_name}\n"
    )
    return subject, body


def format_booking_confirmation_notification(
    candidate_name: str,
    job_title: str,
    organization_name: str,
    scheduled_start: datetime,
    duration_minutes: int,
    timezone_name: str,
    interview_reference: str,
    meeting_url: Optional[str] = None,
    location: Optional[str] = None,
    interview_type: str = "ONLINE",
) -> tuple[str, str]:
    """Formats self-booking confirmation email."""
    date_str = scheduled_start.strftime("%A, %B %d, %Y")
    time_str = scheduled_start.strftime("%I:%M %p")

    subject = f"Booking Confirmed ({interview_reference}): {job_title} at {organization_name}"

    body = DEMO_DISCLAIMER_HEADER
    body += f"Dear {candidate_name},\n\n"
    body += f"Thank you for self-selecting your interview time slot for the {job_title} position.\n\n"
    body += "--- CONFIRMED APPOINTMENT ---\n"
    body += f"• Reference: {interview_reference}\n"
    body += f"• Date: {date_str}\n"
    body += f"• Time: {time_str} ({timezone_name})\n"
    body += f"• Duration: {duration_minutes} minutes\n"

    if interview_type.upper() == "ONLINE" and meeting_url:
        body += f"• Demo Meeting Link: {meeting_url}\n"
    elif location:
        body += f"• Location: {location}\n"

    body += (
        "\nYou can manage or reschedule this appointment using your personalized booking link if required.\n\n"
        f"Sincerely,\n"
        f"{organization_name} Recruiting\n"
    )
    return subject, body


async def record_simulated_notification(
    session: AsyncSession,
    organization_id: UUID,
    recipient: str,
    recipient_name: Optional[str],
    subject: str,
    body: str,
    interview_reference: str,
    notification_type: str,
    interview_schedule_id: Optional[UUID] = None,
    idempotency_key: Optional[str] = None,
) -> SimulatedNotification:
    """
    Persists a simulated email record.
    Prevents duplicate notifications using idempotency checks.
    """
    if idempotency_key:
        stmt = select(SimulatedNotification).where(
            SimulatedNotification.idempotency_key == idempotency_key
        )
        existing = await session.scalar(stmt)
        if existing is not None:
            logger.info(f"Notification with idempotency key '{idempotency_key}' already recorded.")
            return existing

    record = SimulatedNotification(
        id=uuid4(),
        organization_id=organization_id,
        interview_schedule_id=interview_schedule_id,
        recipient=recipient,
        recipient_name=recipient_name,
        subject=subject,
        body=body,
        interview_reference=interview_reference,
        notification_type=notification_type,
        delivery_mode="DEMO_SIMULATED",
        delivery_status="DELIVERED",
        demo_banner="DEMO MODE — EMAILS NOT SENT",
        idempotency_key=idempotency_key,
    )
    session.add(record)
    await session.flush()
    return record
