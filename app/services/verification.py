from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.capability import Capability
from app.models.job import Job
from app.models.verification import Verification
from app.schemas.verification import (
    VerificationCreate,
    VerificationReview,
    VerificationStatus,
    VerificationSubmit,
)
from app.services.application import ApplicationNotFoundError


class InvalidCapabilityError(Exception):
    pass


class VerificationNotFoundError(Exception):
    pass


class InvalidStateTransitionError(Exception):
    pass


async def get_verification_by_id_and_tenant(
    session: AsyncSession,
    verification_id: UUID,
    organization_id: UUID,
) -> Verification:
    stmt = (
        select(Verification)
        .join(Application, Application.id == Verification.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            Verification.id == verification_id,
            Job.organization_id == organization_id,
        )
    )
    verification = await session.scalar(stmt)
    if verification is None:
        raise VerificationNotFoundError("Verification not found")
    return verification


async def create_verification(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    data: VerificationCreate,
) -> Verification:
    # 1. Verify application and tenant ownership
    stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found")

    # 2. Verify capability belongs to application's job
    cap_stmt = select(Capability).where(
        Capability.id == data.capability_id,
        Capability.job_id == application.job_id,
    )
    capability = await session.scalar(cap_stmt)
    if capability is None:
        raise InvalidCapabilityError("Capability does not belong to application's job")

    v_type_str = data.type.value if hasattr(data.type, "value") else str(data.type)

    verification = Verification(
        application_id=application.id,
        capability_id=capability.id,
        type=v_type_str,
        status=VerificationStatus.REQUESTED.value,
        instructions=data.instructions,
        requested_by=user_id,
    )

    session.add(verification)
    await session.commit()
    await session.refresh(verification)
    return verification


async def list_application_verifications(
    session: AsyncSession,
    application_id: UUID,
    organization_id: UUID,
) -> Sequence[Verification]:
    stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == application_id,
            Job.organization_id == organization_id,
        )
    )
    application = await session.scalar(stmt)
    if application is None:
        raise ApplicationNotFoundError("Application not found")

    v_stmt = (
        select(Verification)
        .where(Verification.application_id == application.id)
        .order_by(Verification.created_at.desc())
    )
    result = await session.scalars(v_stmt)
    return result.all()


async def start_verification(
    session: AsyncSession,
    verification_id: UUID,
    organization_id: UUID,
) -> Verification:
    verification = await get_verification_by_id_and_tenant(
        session=session,
        verification_id=verification_id,
        organization_id=organization_id,
    )

    if verification.status != VerificationStatus.REQUESTED.value:
        raise InvalidStateTransitionError(
            f"Cannot start verification in '{verification.status}' status; must be REQUESTED"
        )

    verification.status = VerificationStatus.IN_PROGRESS.value
    verification.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(verification)
    return verification


async def submit_verification(
    session: AsyncSession,
    verification_id: UUID,
    organization_id: UUID,
    data: VerificationSubmit,
) -> Verification:
    verification = await get_verification_by_id_and_tenant(
        session=session,
        verification_id=verification_id,
        organization_id=organization_id,
    )

    if verification.status != VerificationStatus.IN_PROGRESS.value:
        raise InvalidStateTransitionError(
            f"Cannot submit verification in '{verification.status}' status; must be IN_PROGRESS"
        )

    verification.status = VerificationStatus.SUBMITTED.value
    verification.submission_content = data.submission_content
    verification.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(verification)
    return verification


async def review_verification(
    session: AsyncSession,
    verification_id: UUID,
    organization_id: UUID,
    reviewer_id: UUID,
    data: VerificationReview,
) -> Verification:
    verification = await get_verification_by_id_and_tenant(
        session=session,
        verification_id=verification_id,
        organization_id=organization_id,
    )

    if verification.status != VerificationStatus.SUBMITTED.value:
        raise InvalidStateTransitionError(
            f"Cannot review verification in '{verification.status}' status; must be SUBMITTED"
        )

    result_str = data.result.value if hasattr(data.result, "value") else str(data.result)

    verification.status = VerificationStatus.REVIEWED.value
    verification.result = result_str
    verification.review_notes = data.review_notes
    verification.reviewed_by = reviewer_id
    verification.completed_at = datetime.utcnow()
    verification.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(verification)
    return verification


async def cancel_verification(
    session: AsyncSession,
    verification_id: UUID,
    organization_id: UUID,
) -> Verification:
    verification = await get_verification_by_id_and_tenant(
        session=session,
        verification_id=verification_id,
        organization_id=organization_id,
    )

    allowed_cancel_statuses = {
        VerificationStatus.REQUESTED.value,
        VerificationStatus.IN_PROGRESS.value,
        VerificationStatus.SUBMITTED.value,
    }

    if verification.status not in allowed_cancel_statuses:
        raise InvalidStateTransitionError(
            f"Cannot cancel verification in '{verification.status}' status"
        )

    verification.status = VerificationStatus.CANCELLED.value
    verification.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(verification)
    return verification
