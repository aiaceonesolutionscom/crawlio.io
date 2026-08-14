from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import get_admin_permissions, get_current_admin
from app.core.permissions import ROLE_SUPER_ADMIN
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import WhoamiRead

router = APIRouter()


@router.get("/whoami", response_model=WhoamiRead)
async def whoami(
    admin: Annotated[PlatformAdmin, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    perms = sorted(await get_admin_permissions(session, admin))
    return WhoamiRead(
        email=admin.email,
        role=admin.role,
        is_super_admin=admin.role == ROLE_SUPER_ADMIN,
        permissions=perms,
    )