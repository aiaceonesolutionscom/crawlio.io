import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 (populates Base.metadata)
from app.core.deps import get_current_user_id
from app.db.base import Base
from app.db.session import get_session
from app.main import app

TEST_USER_ID = "user_test_fixed"


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
