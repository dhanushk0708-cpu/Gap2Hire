from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.evidence_research.schemas import ResearchRunResult
from app.agents.evidence_research.service import run_evidence_research
from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.research_state import (
    ResearchCapabilityStateResponse,
    ResearchCapabilityStateUpdate,
    ResearchEventCreate,
    ResearchEventResponse,
    ResearchSessionCreate,
    ResearchSessionDetailResponse,
    ResearchSessionResponse,
    ResearchSessionUpdate,
)
from app.services.research_state import (
    ApplicationNotFoundError,
    InvalidCapabilityError,
    InvalidSourceTenantError,
    ResearchCapabilityStateNotFoundError,
    ResearchSessionNotFoundError,
    create_research_event,
    create_research_session,
    get_capability_states,
    get_research_events,
    get_research_session,
    update_capability_state,
    update_research_session,
)

router = APIRouter(
    tags=["Research Sessions & State"],
)

require_research_manager = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@router.post(
    "/api/v1/research-sessions/{session_id}/run",
    response_model=ResearchRunResult,
    status_code=status.HTTP_200_OK,
)
async def run_evidence_research_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_research_manager),
):
    try:
        return await run_evidence_research(
            session_id=session_id,
            organization_id=current_user.organization_id,
        )
    except ResearchSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e



@router.post(
    "/api/v1/applications/{application_id}/research-sessions",
    response_model=ResearchSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_research_session_endpoint(
    application_id: UUID,
    data: Optional[ResearchSessionCreate] = None,
    current_user: User = Depends(require_research_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await create_research_session(
            session=session,
            organization_id=current_user.organization_id,
            application_id=application_id,
            data=data or ResearchSessionCreate(),
        )
    except ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/research-sessions/{session_id}",
    response_model=ResearchSessionDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_research_session_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_research_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_research_session(
            session=session,
            organization_id=current_user.organization_id,
            session_id=session_id,
            load_details=True,
        )
    except ResearchSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch(
    "/api/v1/research-sessions/{session_id}",
    response_model=ResearchSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def update_research_session_endpoint(
    session_id: UUID,
    data: ResearchSessionUpdate,
    current_user: User = Depends(require_research_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await update_research_session(
            session=session,
            organization_id=current_user.organization_id,
            session_id=session_id,
            data=data,
        )
    except ResearchSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/research-sessions/{session_id}/capabilities",
    response_model=list[ResearchCapabilityStateResponse],
    status_code=status.HTTP_200_OK,
)
async def get_capability_states_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_research_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_capability_states(
            session=session,
            organization_id=current_user.organization_id,
            session_id=session_id,
        )
    except ResearchSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch(
    "/api/v1/research-sessions/{session_id}/capabilities/{capability_id}",
    response_model=ResearchCapabilityStateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_capability_state_endpoint(
    session_id: UUID,
    capability_id: UUID,
    data: ResearchCapabilityStateUpdate,
    current_user: User = Depends(require_research_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await update_capability_state(
            session=session,
            organization_id=current_user.organization_id,
            session_id=session_id,
            capability_id=capability_id,
            state=data.state,
            reason=data.reason,
        )
    except (ResearchSessionNotFoundError, ResearchCapabilityStateNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/api/v1/research-sessions/{session_id}/events",
    response_model=list[ResearchEventResponse],
    status_code=status.HTTP_200_OK,
)
async def get_research_events_endpoint(
    session_id: UUID,
    current_user: User = Depends(require_research_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_research_events(
            session=session,
            organization_id=current_user.organization_id,
            session_id=session_id,
        )
    except ResearchSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/api/v1/research-sessions/{session_id}/events",
    response_model=ResearchEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_research_event_endpoint(
    session_id: UUID,
    data: ResearchEventCreate,
    current_user: User = Depends(require_research_manager),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await create_research_event(
            session=session,
            organization_id=current_user.organization_id,
            session_id=session_id,
            event_type=data.event_type,
            source_id=data.source_id,
            capability_id=data.capability_id,
            message=data.message,
            metadata=data.metadata,
        )
    except ResearchSessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (InvalidSourceTenantError, InvalidCapabilityError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
