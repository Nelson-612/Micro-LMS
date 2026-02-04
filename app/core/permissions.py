from fastapi import Depends, HTTPException, status

from app.core.current_user import get_current_user
from app.models.user import User


def require_instructor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor role required",
        )
    return current_user