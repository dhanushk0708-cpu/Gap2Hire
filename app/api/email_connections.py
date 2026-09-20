from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.email_integration import (
    BatchEmailSyncResponse,
    EmailConnectionCreate,
    EmailConnectionResponse,
    EmailIntakeResult,
)
from app.services.email_connection import (
    EmailConnectionNotFoundError,
    create_email_connection,
    delete_email_connection,
    get_email_connection,
    list_email_connections,
)
from app.services.email_intake import batch_sync_emails, process_email_intake
from app.services.email_provider import FakeEmailProvider

router = APIRouter(prefix="/api/v1/email-connections", tags=["Email Connections"])
email_router = APIRouter(prefix="/api/v1/email", tags=["Email Sync"])

require_hr = require_roles(
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
)


@email_router.post(
    "/sync",
    response_model=BatchEmailSyncResponse,
    status_code=status.HTTP_200_OK,
)
async def load_new_resumes_endpoint(
    limit: int = 10,
    target_job_id: UUID | None = None,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Company-level 'LOAD NEW RESUMES' action. Synchronizes a bounded batch of emails and executes candidate intake."""
    return await batch_sync_emails(
        session=session,
        organization_id=current_user.organization_id,
        limit=limit,
        target_job_id=target_job_id,
    )


@router.post(
    "",
    response_model=EmailConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection_endpoint(
    body: EmailConnectionCreate,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    return await create_email_connection(
        session=session,
        organization_id=current_user.organization_id,
        data=body,
    )


@router.get(
    "",
    response_model=list[EmailConnectionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_connections_endpoint(
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    return await list_email_connections(
        session=session,
        organization_id=current_user.organization_id,
    )


@router.get(
    "/{connection_id}",
    response_model=EmailConnectionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_connection_endpoint(
    connection_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_email_connection(
            session=session,
            connection_id=connection_id,
            organization_id=current_user.organization_id,
        )
    except EmailConnectionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_connection_endpoint(
    connection_id: UUID,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        await delete_email_connection(
            session=session,
            connection_id=connection_id,
            organization_id=current_user.organization_id,
        )
    except EmailConnectionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/oauth/google/url",
    status_code=status.HTTP_200_OK,
)
async def get_google_oauth_url_endpoint(
    state: str = "",
    current_user: User = Depends(require_hr),
):
    """Generates the Google OAuth authorization URL for connecting Gmail."""
    from app.services.gmail_provider import get_google_auth_url
    url = get_google_auth_url(state=state or str(current_user.organization_id))
    return {"authorization_url": url}


@router.get(
    "/oauth/callback",
    response_model=EmailConnectionResponse,
    status_code=status.HTTP_200_OK,
)
async def google_oauth_callback_endpoint(
    code: str,
    state: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """Handles the Google OAuth redirect callback, exchanges token, and saves the Gmail connection."""
    import json
    from app.models.organization import Organization
    from app.services.gmail_provider import exchange_google_code_for_tokens

    try:
        token_data = await exchange_google_code_for_tokens(code)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth token exchange failed: {exc}",
        ) from exc

    # Resolve organization from state or fallback to default
    org_id = None
    if state:
        try:
            org_id = UUID(state)
        except Exception:
            pass

    if not org_id:
        org_stmt = select(Organization).limit(1)
        org = await session.scalar(org_stmt)
        if org:
            org_id = org.id

    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine organization for OAuth connection.",
        )

    # Save connection
    conn_data = EmailConnectionCreate(
        provider="GMAIL",
        account_email=token_data.get("account_email", "connected-gmail@gap2hire.com"),
        status="ACTIVE",
        auth_payload_encrypted=json.dumps({
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
        }),
    )

    return await create_email_connection(
        session=session,
        organization_id=org_id,
        data=conn_data,
    )


@router.post(
    "/{connection_id}/sync",
    response_model=BatchEmailSyncResponse,
    status_code=status.HTTP_200_OK,
)
async def sync_emails_endpoint(
    connection_id: UUID,
    limit: int = 10,
    target_job_id: UUID | None = None,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Synchronizes bounded emails from the specific connection and executes candidate intake."""
    try:
        await get_email_connection(
            session=session,
            connection_id=connection_id,
            organization_id=current_user.organization_id,
        )
    except EmailConnectionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return await batch_sync_emails(
        session=session,
        organization_id=current_user.organization_id,
        connection_id=connection_id,
        limit=limit,
        target_job_id=target_job_id,
    )


@router.post(
    "/{connection_id}/sync-fake",
    response_model=BatchEmailSyncResponse,
    status_code=status.HTTP_200_OK,
)
async def sync_fake_emails_endpoint(
    connection_id: UUID,
    limit: int = 10,
    target_job_id: UUID | None = None,
    current_user: User = Depends(require_hr),
    session: AsyncSession = Depends(get_db_session),
):
    """Fetches deterministic synthetic emails and processes intake under tenant isolation."""
    return await sync_emails_endpoint(
        connection_id=connection_id,
        limit=limit,
        target_job_id=target_job_id,
        current_user=current_user,
        session=session,
    )

