from fastapi import APIRouter, Depends

from app.core.permissions import require_instructor
from app.models.user import User

router = APIRouter()


@router.get("/ping")
def admin_ping(current_user: User = Depends(require_instructor)):
    return {"msg": "admin ok", "user": current_user.email}
