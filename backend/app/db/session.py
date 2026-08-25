from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

connect_args = {"ssl": False} if "postgresql" in settings.database_url else {}
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args=connect_args,
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
