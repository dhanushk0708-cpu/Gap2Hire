from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import RegisterRequest


async def register_user(
    session: AsyncSession,
    data: RegisterRequest,
) -> User:
    existing_user = await session.scalar(
        select(User).where(User.email == data.email)
    )

    if existing_user:
        raise ValueError("User with this email already exists")

    organization = Organization(
        name=data.organization_name,
        slug=data.organization_name.lower().replace(" ", "-"),
    )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role="COMPANY_ADMIN",
    )

    organization.users.append(user)

    session.add(organization)

    await session.commit()
    await session.refresh(user)

    return user


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    user = await session.scalar(
        select(User).where(User.email == email)
    )

    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user