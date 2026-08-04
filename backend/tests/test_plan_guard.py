import pytest
from fastapi import HTTPException

from app.core.deps import require_plan
from app.db.models.workspace import Workspace


def _workspace(plan: str) -> Workspace:
    return Workspace(id="ws_1", name="Test", plan=plan, lead_quota=500, seat_quota=1)


def test_require_plan_allows_when_capability_included():
    dependency = require_plan("automation")
    workspace = _workspace("pro")
    assert dependency(workspace) is workspace


def test_require_plan_blocks_when_capability_missing():
    dependency = require_plan("automation")
    with pytest.raises(HTTPException) as exc_info:
        dependency(_workspace("free"))
    assert exc_info.value.status_code == 403


def test_require_plan_enterprise_only_capability():
    dependency = require_plan("branding")
    assert dependency(_workspace("enterprise")) is not None
    with pytest.raises(HTTPException) as exc_info:
        dependency(_workspace("pro"))
    assert exc_info.value.status_code == 403


def test_require_plan_free_has_base_capabilities():
    dependency = require_plan("leads")
    assert dependency(_workspace("free")) is not None
