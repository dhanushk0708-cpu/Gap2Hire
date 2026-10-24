from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_roles
from app.core.roles import UserRole
from app.db.session import get_db_session
from app.models.email_connection import EmailConnection
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
    try:
        return await batch_sync_emails(
            session=session,
            organization_id=current_user.organization_id,
            limit=limit,
            target_job_id=target_job_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        from app.services.gmail_provider import GmailAuthenticationError, GmailSyncError

        if isinstance(exc, GmailAuthenticationError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        elif isinstance(exc, GmailSyncError):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email sync failed: {exc}",
        ) from exc


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
    """Generates the Google OAuth authorization URL for connecting Gmail with CSRF state token."""
    from app.core.security import generate_oauth_state
    from app.services.gmail_provider import get_google_auth_url

    try:
        oauth_state = generate_oauth_state(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
        )
        url = get_google_auth_url(state=oauth_state)
        return {"authorization_url": url}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/oauth/callback",
    response_model=EmailConnectionResponse,
    status_code=status.HTTP_200_OK,
)
async def google_oauth_callback_endpoint(
    request: Request,
    code: str,
    state: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """Handles Google OAuth callback, validates CSRF state, exchanges tokens, encrypts payload, and marks connection ACTIVE."""
    from datetime import datetime
    from app.core.config import settings
    from app.core.security import encrypt_auth_payload, validate_oauth_state
    from app.models.organization import Organization
    from app.services.gmail_provider import exchange_google_code_for_tokens
    from fastapi.responses import HTMLResponse

    accept_header = request.headers.get("accept", "")
    is_browser = "text/html" in accept_header

    # Validate state to prevent CSRF and isolate to authenticating organization
    try:
        state_payload = validate_oauth_state(state)
        org_id = UUID(state_payload["org_id"])
    except Exception as exc:
        if is_browser:
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html><head><title>OAuth Failed</title></head>
                <body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh;">
                  <div style="text-align: center; max-width: 450px; padding: 2rem; border: 1px solid #FCA5A5; border-radius: 8px; background: #FEF2F2;">
                    <h2 style="color: #991B1B;">OAuth Authorization Failed</h2>
                    <p style="color: #7F1D1D;">Invalid or expired CSRF state. {exc}</p>
                    <a href="{settings.frontend_url.rstrip('/')}/settings/email" style="display: inline-block; margin-top: 1rem; color: #2563EB;">Return to Email Settings</a>
                  </div>
                </body></html>
                """,
                status_code=400,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSRF state validation failed: {exc}",
        ) from exc

    org = await session.get(Organization, org_id)
    if not org:
        stmt = select(Organization).where(Organization.id == org_id)
        org = await session.scalar(stmt)
    if not org:
        if is_browser:
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html><head><title>Organization Not Found</title></head>
                <body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh;">
                  <div style="text-align: center; max-width: 450px; padding: 2rem; border: 1px solid #FCA5A5; border-radius: 8px; background: #FEF2F2;">
                    <h2 style="color: #991B1B;">Organization Not Found</h2>
                    <p style="color: #7F1D1D;">Organization {org_id} associated with this OAuth session was not found.</p>
                    <a href="{settings.frontend_url.rstrip('/')}/settings/email" style="display: inline-block; margin-top: 1rem; color: #2563EB;">Return to Email Settings</a>
                  </div>
                </body></html>
                """,
                status_code=404,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target organization not found.",
        )

    try:
        token_data = await exchange_google_code_for_tokens(code)
    except Exception as exc:
        if is_browser:
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html><head><title>Token Exchange Failed</title></head>
                <body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh;">
                  <div style="text-align: center; max-width: 450px; padding: 2rem; border: 1px solid #FCA5A5; border-radius: 8px; background: #FEF2F2;">
                    <h2 style="color: #991B1B;">Token Exchange Failed</h2>
                    <p style="color: #7F1D1D;">{exc}</p>
                    <a href="{settings.frontend_url.rstrip('/')}/settings/email" style="display: inline-block; margin-top: 1rem; color: #2563EB;">Return to Email Settings</a>
                  </div>
                </body></html>
                """,
                status_code=400,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth token exchange failed: {exc}",
        ) from exc

    account_email = token_data.get("account_email", "connected-gmail@gap2hire.com")
    encrypted_tokens = encrypt_auth_payload({
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "token_type": token_data.get("token_type", "Bearer"),
        "scope": token_data.get("scope"),
    })

    # Search for an existing Gmail connection for this tenant organization
    stmt = (
        select(EmailConnection)
        .where(
            EmailConnection.organization_id == org_id,
            EmailConnection.provider == "GMAIL",
        )
        .order_by(EmailConnection.created_at.desc())
    )
    existing_conn = await session.scalar(stmt)

    if existing_conn:
        existing_conn.account_email = account_email.strip().lower()
        existing_conn.status = "ACTIVE"
        existing_conn.auth_payload_encrypted = encrypted_tokens
        existing_conn.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(existing_conn)
        conn_record = existing_conn
    else:
        conn_record = EmailConnection(
            organization_id=org_id,
            provider="GMAIL",
            account_email=account_email.strip().lower(),
            status="ACTIVE",
            auth_payload_encrypted=encrypted_tokens,
        )
        session.add(conn_record)
        await session.commit()
        await session.refresh(conn_record)

    if is_browser:
        redirect_url = f"{settings.frontend_url.rstrip('/')}/settings/email?gmail_connected=true"
        html_page = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Gmail Connected - Gap2Hire</title>
            <meta http-equiv="refresh" content="2;url={redirect_url}" />
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #F8FAFC; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                .card {{ background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 36px 48px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); max-width: 440px; }}
                .icon {{ width: 52px; height: 52px; border-radius: 50%; background: #DCFCE7; color: #16A34A; display: inline-flex; align-items: center; justify-content: center; font-size: 26px; margin: 0 auto 16px auto; }}
                h2 {{ color: #0F172A; font-size: 20px; font-weight: 600; margin: 0 0 8px 0; }}
                p {{ color: #64748B; font-size: 14px; margin: 0 0 24px 0; line-height: 1.5; }}
                .btn {{ display: inline-block; background: #2563EB; color: #FFFFFF; padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; text-decoration: none; transition: background 0.15s; }}
                .btn:hover {{ background: #1D4ED8; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✓</div>
                <h2>Gmail Connected Successfully!</h2>
                <p>Your Gmail account (<strong>{account_email}</strong>) has been securely linked to Gap2Hire with active status.</p>
                <a class="btn" href="{redirect_url}">Continue to Email Settings</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_page)

    return conn_record


@email_router.get(
    "/oauth/callback",
    response_model=EmailConnectionResponse,
    status_code=status.HTTP_200_OK,
)
async def email_oauth_callback_alias(
    request: Request,
    code: str,
    state: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """Alias for /api/v1/email/oauth/callback matching Google OAuth client credentials."""
    return await google_oauth_callback_endpoint(
        request=request,
        code=code,
        state=state,
        session=session,
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

    try:
        return await batch_sync_emails(
            session=session,
            organization_id=current_user.organization_id,
            connection_id=connection_id,
            limit=limit,
            target_job_id=target_job_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        from app.services.gmail_provider import GmailAuthenticationError, GmailSyncError

        if isinstance(exc, GmailAuthenticationError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        elif isinstance(exc, GmailSyncError):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email sync failed: {exc}",
        ) from exc


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

