from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.core.roles import UserRole
from app.models.user import User


def require_roles(*allowed_roles: str | UserRole) -> Callable:
    normalized_roles = {
        r.value if isinstance(r, UserRole) else str(r)
        for r in allowed_roles
    }

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role = (
            current_user.role.value
            if isinstance(current_user.role, UserRole)
            else str(current_user.role)
        )
        if user_role not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return current_user

    return role_checker