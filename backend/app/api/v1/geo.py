from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_workspace
from app.db.models.workspace import Workspace
from app.services import geo_service

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/countries")
async def list_countries(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    q: Optional[str] = Query(default=None),
):
    return {"items": geo_service.search_countries(q)}


@router.get("/cities")
async def list_cities(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    country: str = Query(...),
    q: str = Query(...),
):
    return {"items": geo_service.search_cities(country, q)}
