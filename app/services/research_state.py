from collections.abc import Sequence
from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate_source import CandidateSource
from app.models.capability import Capability
from app.models.job import Job
from app.models.research_capability import ResearchCapabilityState
from app.models.research_event import ResearchEvent
from app.models.research_session import ResearchSession
from app.schemas.research_state import (
    ResearchCapabilityStateUpdate,
    ResearchEventCreate,
    ResearchSessionCreate,
    ResearchSessionUpdate,
)


class ResearchSessionNotFoundError(Exception):
    pass


class ResearchCapabilityStateNotFoundError(Exception):
    pass


class ApplicationNotFoundError(Exception):
    pass


class InvalidSourceTenantError(Exception):
    pass


class InvalidCapabilityError(Exception):
    pass


async def _get_tenant_application(
    session: AsyncSession,
    application_id: Union[UUID, str],
    organization_id: Union[UUID, str],
) -> Application:
    """Verifies that the application exists and belongs to the given tenant organization."""
    app_uuid = UUID(str(application_id)) if not isinstance(application_id, UUID) else application_id
    org_uuid = UUID(str(organization_id)) if not isinstance(organization_id, UUID) else organization_id

    stmt = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.id == app_uuid,
            Job.organization_id == org_uuid,
        )
    )
    application = await session.scalar(stmt)
    if application is None:
        raise ApplicationNotFoundError(f"Application {app_uuid} not found")
    return application


async def _get_tenant_research_session(
    session: AsyncSession,
    session_id: Union[UUID, str],
    organization_id: Union[UUID, str],
    load_details: bool = False,
) -> ResearchSession:
    """Verifies that the research session exists and belongs to the given tenant organization."""
    sess_uuid = UUID(str(session_id)) if not isinstance(session_id, UUID) else session_id
    org_uuid = UUID(str(organization_id)) if not isinstance(organization_id, UUID) else organization_id

    stmt = (
        select(ResearchSession)
        .join(Application, Application.id == ResearchSession.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            ResearchSession.id == sess_uuid,
            Job.organization_id == org_uuid,
        )
    )
    if load_details:
        stmt = stmt.options(
            selectinload(ResearchSession.capability_states),
            selectinload(ResearchSession.events),
        )

    res_session = await session.scalar(stmt)
    if res_session is None:
        raise ResearchSessionNotFoundError(f"Research session {sess_uuid} not found")
    return res_session


async def create_research_session(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    application_id: Union[UUID, str],
    data: Optional[Union[ResearchSessionCreate, dict[str, Any]]] = None,
) -> ResearchSession:
    """
    Creates a persistent research session for an application under tenant isolation,
    initializes all required job capabilities to UNKNOWN state, and logs the initial event.
    """
    application = await _get_tenant_application(session, application_id, organization_id)

    metadata_val = None
    if data is not None:
        if isinstance(data, ResearchSessionCreate):
            metadata_val = data.metadata
        elif isinstance(data, dict):
            metadata_val = data.get("metadata")

    res_session = ResearchSession(
        application_id=application.id,
        status="PENDING",
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        metadata_=metadata_val,
    )
    session.add(res_session)
    await session.flush()

    # Initialize capability states for all capabilities belonging to the application's job
    caps_stmt = select(Capability).where(Capability.job_id == application.job_id)
    capabilities = (await session.scalars(caps_stmt)).all()

    for cap in capabilities:
        cap_state = ResearchCapabilityState(
            research_session_id=res_session.id,
            capability_id=cap.id,
            state="UNKNOWN",
        )
        session.add(cap_state)

    # Record initial lifecycle event
    initial_event = ResearchEvent(
        research_session_id=res_session.id,
        event_type="SESSION_STARTED",
        message="Research session initialized in PENDING state.",
    )
    session.add(initial_event)

    await session.commit()
    await session.refresh(res_session)
    return res_session


async def get_research_session(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    session_id: Union[UUID, str],
    load_details: bool = False,
) -> ResearchSession:
    """Retrieves a research session under tenant isolation."""
    return await _get_tenant_research_session(
        session, session_id, organization_id, load_details=load_details
    )


async def update_research_session(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    session_id: Union[UUID, str],
    data: Union[ResearchSessionUpdate, dict[str, Any]],
) -> ResearchSession:
    """Updates fields and status on a research session with tenant isolation."""
    res_session = await _get_tenant_research_session(session, session_id, organization_id)

    update_dict = data.model_dump(exclude_unset=True) if isinstance(data, ResearchSessionUpdate) else data

    if "status" in update_dict and update_dict["status"] is not None:
        res_session.status = update_dict["status"]
        if update_dict["status"] in {"COMPLETED", "FAILED", "CANCELLED"} and not res_session.completed_at:
            res_session.completed_at = datetime.utcnow()
    if "current_source_id" in update_dict:
        res_session.current_source_id = update_dict["current_source_id"]
    if "stop_reason" in update_dict:
        res_session.stop_reason = update_dict["stop_reason"]
    if "metadata" in update_dict:
        res_session.metadata_ = update_dict["metadata"]
    if "completed_at" in update_dict and update_dict["completed_at"] is not None:
        res_session.completed_at = update_dict["completed_at"]

    res_session.last_activity_at = datetime.utcnow()
    res_session.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(res_session)
    return res_session


async def initialize_capability_states(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    session_id: Union[UUID, str],
) -> Sequence[ResearchCapabilityState]:
    """
    Ensures all capabilities belonging to the application's job are initialized
    in UNKNOWN state for this research session.
    """
    res_session = await _get_tenant_research_session(session, session_id, organization_id)

    # Get application's job_id
    app_stmt = select(Application.job_id).where(Application.id == res_session.application_id)
    job_id = await session.scalar(app_stmt)

    caps_stmt = select(Capability).where(Capability.job_id == job_id)
    capabilities = (await session.scalars(caps_stmt)).all()

    existing_stmt = select(ResearchCapabilityState.capability_id).where(
        ResearchCapabilityState.research_session_id == res_session.id
    )
    existing_cap_ids = set((await session.scalars(existing_stmt)).all())

    created_states: list[ResearchCapabilityState] = []
    for cap in capabilities:
        if cap.id not in existing_cap_ids:
            cap_state = ResearchCapabilityState(
                research_session_id=res_session.id,
                capability_id=cap.id,
                state="UNKNOWN",
            )
            session.add(cap_state)
            created_states.append(cap_state)

    if created_states:
        res_session.last_activity_at = datetime.utcnow()
        await session.commit()

    all_stmt = select(ResearchCapabilityState).where(
        ResearchCapabilityState.research_session_id == res_session.id
    )
    return (await session.scalars(all_stmt)).all()


async def get_capability_states(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    session_id: Union[UUID, str],
) -> Sequence[ResearchCapabilityState]:
    """Returns all capability states for a research session under tenant isolation."""
    res_session = await _get_tenant_research_session(session, session_id, organization_id)
    stmt = (
        select(ResearchCapabilityState)
        .where(ResearchCapabilityState.research_session_id == res_session.id)
        .order_by(ResearchCapabilityState.created_at.asc())
    )
    return (await session.scalars(stmt)).all()


async def update_capability_state(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    session_id: Union[UUID, str],
    capability_id: Union[UUID, str],
    state: str,
    reason: Optional[str] = None,
) -> ResearchCapabilityState:
    """
    Updates the investigation state and reasoning for a capability within a research session.
    """
    res_session = await _get_tenant_research_session(session, session_id, organization_id)
    cap_uuid = UUID(str(capability_id)) if not isinstance(capability_id, UUID) else capability_id

    stmt = select(ResearchCapabilityState).where(
        ResearchCapabilityState.research_session_id == res_session.id,
        ResearchCapabilityState.capability_id == cap_uuid,
    )
    cap_state = await session.scalar(stmt)
    if cap_state is None:
        raise ResearchCapabilityStateNotFoundError(
            f"Capability state for capability {cap_uuid} in session {res_session.id} not found"
        )

    cap_state.state = state
    if reason is not None:
        cap_state.reason = reason
    cap_state.last_checked_at = datetime.utcnow()
    cap_state.updated_at = datetime.utcnow()
    res_session.last_activity_at = datetime.utcnow()

    await session.commit()
    await session.refresh(cap_state)
    return cap_state


async def create_research_event(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    session_id: Union[UUID, str],
    event_type: str,
    source_id: Optional[Union[UUID, str]] = None,
    capability_id: Optional[Union[UUID, str]] = None,
    message: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> ResearchEvent:
    """
    Appends a new research audit event to the research session history under tenant isolation.
    """
    res_session = await _get_tenant_research_session(session, session_id, organization_id)

    src_uuid = UUID(str(source_id)) if source_id is not None and not isinstance(source_id, UUID) else source_id
    cap_uuid = UUID(str(capability_id)) if capability_id is not None and not isinstance(capability_id, UUID) else capability_id

    if src_uuid is not None:
        src_stmt = select(CandidateSource).where(CandidateSource.id == src_uuid)
        source = await session.scalar(src_stmt)
        if source is None or source.application_id != res_session.application_id:
            raise InvalidSourceTenantError(f"Candidate source {src_uuid} does not belong to this application")

    if cap_uuid is not None:
        app_stmt = select(Application.job_id).where(Application.id == res_session.application_id)
        job_id = await session.scalar(app_stmt)
        cap_stmt = select(Capability).where(Capability.id == cap_uuid, Capability.job_id == job_id)
        capability = await session.scalar(cap_stmt)
        if capability is None:
            raise InvalidCapabilityError(f"Capability {cap_uuid} does not belong to this application's job")

    event = ResearchEvent(
        research_session_id=res_session.id,
        event_type=event_type,
        source_id=src_uuid,
        capability_id=cap_uuid,
        message=message,
        metadata_=metadata,
    )
    session.add(event)
    res_session.last_activity_at = datetime.utcnow()

    await session.commit()
    await session.refresh(event)
    return event


async def get_research_events(
    session: AsyncSession,
    organization_id: Union[UUID, str],
    session_id: Union[UUID, str],
) -> Sequence[ResearchEvent]:
    """Returns all audit events for a research session in chronological order."""
    res_session = await _get_tenant_research_session(session, session_id, organization_id)
    stmt = (
        select(ResearchEvent)
        .where(ResearchEvent.research_session_id == res_session.id)
        .order_by(ResearchEvent.created_at.asc())
    )
    return (await session.scalars(stmt)).all()
