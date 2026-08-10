import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.deps import require_plan
from app.db.models.workspace import Workspace


def _workspace(plan: str) -> Workspace:
    return Workspace(id="ws_1", name="Test", plan=plan, lead_quota=500, seat_quota=1)


@pytest.fixture
async def session(db_engine):
    """require_plan's dependency reads capabilities from the DB, so unit-testing
    it needs a real session backed by the seeded plan_configs — same engine the
    other fixtures use, just without going through the HTTP client."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as s:
        yield s


async def test_require_plan_allows_when_capability_included(session):
    dependency = require_plan("automation")
    workspace = _workspace("pro")
    assert await dependency(workspace, session) is workspace


async def test_require_plan_blocks_when_capability_missing(session):
    dependency = require_plan("automation")
    with pytest.raises(HTTPException) as exc_info:
        await dependency(_workspace("free"), session)
    assert exc_info.value.status_code == 403


async def test_require_plan_enterprise_only_capability(session):
    dependency = require_plan("branding")
    assert await dependency(_workspace("enterprise"), session) is not None
    with pytest.raises(HTTPException) as exc_info:
        await dependency(_workspace("pro"), session)
    assert exc_info.value.status_code == 403


async def test_require_plan_free_has_base_capabilities(session):
    dependency = require_plan("leads")
    assert await dependency(_workspace("free"), session) is not None
