import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 (populates Base.metadata)
from app.core.admin_deps import require_super_admin
from app.core.deps import get_current_user_id
from app.db.base import Base
from app.db.models.plan_config import PlanConfig
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.main import app

TEST_USER_ID = "user_test_fixed"
TEST_ADMIN_EMAIL = "admin_test_fixed@crawlio.io"

# Mirrors the seed data inserted by migration f2a3b4c5d6e7 — workspace creation
# looks these up by plan_key and 404s without them, so every test touching
# workspaces/leads/etc. needs this present in the fixture DB too.
_PLAN_SEED = [
    dict(
        plan_key="free", display_name="Free", lead_quota=500, seat_quota=1,
        discovery_result_limit=50, daily_discovery_import_limit=50, daily_email_limit=0,
        capabilities=["leads", "workspaces", "lead_discovery", "export"], sort_order=0,
    ),
    dict(
        plan_key="pro", display_name="Pro", lead_quota=5000, seat_quota=10,
        discovery_result_limit=100, daily_discovery_import_limit=100, daily_email_limit=100,
        capabilities=[
            "leads", "workspaces", "automation", "analytics", "team", "whatsapp", "export",
            "lead_discovery", "lead_discovery_enhanced", "ai_lead_filter", "email_agent",
        ],
        sort_order=1,
    ),
    dict(
        plan_key="enterprise", display_name="Enterprise", lead_quota=1_000_000_000, seat_quota=1_000_000_000,
        discovery_result_limit=200, daily_discovery_import_limit=200, daily_email_limit=500,
        capabilities=[
            "leads", "workspaces", "automation", "analytics", "team", "whatsapp", "branding", "sso", "export",
            "lead_discovery", "lead_discovery_enhanced", "ai_lead_filter", "email_agent",
        ],
        sort_order=2,
    ),
]


@pytest.fixture
async def client():
    """Unauthenticated client, no DB wired up — for tests that don't touch persistence."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for plan in _PLAN_SEED:
            session.add(PlanConfig(id=str(uuid.uuid4()), is_active=True, created_at=now, updated_at=now, **plan))
        await session.commit()

    yield engine
    await engine.dispose()


@pytest.fixture
async def authed_client(db_engine):
    """Client with a real in-memory DB and get_current_user_id pinned to a fixed test user."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_session():
        async with session_maker() as session:
            yield session

    async def override_get_current_user_id():
        return TEST_USER_ID

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def client_factory(db_engine):
    """Yields a function that produces a client acting as an arbitrary user_id, all
    sharing the same in-memory DB — for tests that need multiple distinct workspaces
    (e.g. cross-tenant isolation). Callers must fully finish one client's requests
    before switching users, since the override is a single global mapping."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    def _client_for(user_id: str) -> AsyncClient:
        async def override_get_current_user_id():
            return user_id

        app.dependency_overrides[get_current_user_id] = override_get_current_user_id
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    yield _client_for
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(db_engine):
    """Client authenticated as a seeded PlatformAdmin, for /admin/* routes.
    Bypasses JWT verification entirely by overriding require_super_admin
    directly — resolve_or_bootstrap's claims-based lookup is already covered
    by test_whoami.py, so admin routes don't need to re-prove that path."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        admin = PlatformAdmin(email=TEST_ADMIN_EMAIL, is_active=True, created_at=now)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

    async def override_get_session():
        async with session_maker() as session:
            yield session

    async def override_require_super_admin():
        async with session_maker() as session:
            result = await session.execute(
                select(PlatformAdmin).where(PlatformAdmin.email == TEST_ADMIN_EMAIL)
            )
            return result.scalar_one()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[require_super_admin] = override_require_super_admin
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
