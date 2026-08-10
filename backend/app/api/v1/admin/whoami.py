from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.admin_deps import require_super_admin
from app.db.models.platform_admin import PlatformAdmin
from app.schemas.admin import WhoamiRead

router = APIRouter()


@router.get("/whoami", response_model=WhoamiRead)
async def whoami(admin: Annotated[PlatformAdmin, Depends(require_super_admin)]):
    return WhoamiRead(email=admin.email)
