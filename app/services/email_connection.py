from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_connection import EmailConnection
from app.schemas.email_integration import EmailConnectionCreate


class EmailConnectionNotFoundError(Exception):
    pass


async def create_email_connection(
    session: AsyncSession,
    organization_id: UUID,
    data: EmailConnectionCreate,
) -> EmailConnection:
    """Creates a new tenant-scoped email connection."""
    conn = EmailConnection(
        organization_id=organization_id,
        provider=data.provider.upper(),
        account_email=data.account_email.strip().lower(),
        status=data.status,
        auth_payload_encrypted=data.auth_payload_encrypted,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return conn


async def list_email_connections(
    session: AsyncSession,
    organization_id: UUID,
) -> list[EmailConnection]:
    """Lists email connections belonging strictly to the specified organization."""
    stmt = (
        select(EmailConnection)
        .where(EmailConnection.organization_id == organization_id)
        .order_by(EmailConnection.created_at.desc())
    )
    return list((await session.scalars(stmt)).all())


async def get_email_connection(
    session: AsyncSession,
    connection_id: UUID,
    organization_id: UUID,
) -> EmailConnection:
    """Retrieves an email connection enforcing tenant isolation."""
    stmt = select(EmailConnection).where(
        EmailConnection.id == connection_id,
        EmailConnection.organization_id == organization_id,
    )
    conn = await session.scalar(stmt)
    if not conn:
        raise EmailConnectionNotFoundError("Email connection not found or inaccessible")
    return conn


async def delete_email_connection(
    session: AsyncSession,
    connection_id: UUID,
    organization_id: UUID,
) -> None:
    """Deletes an email connection enforcing tenant isolation."""
    conn = await get_email_connection(session, connection_id, organization_id)
    await session.delete(conn)
    await session.commit()
