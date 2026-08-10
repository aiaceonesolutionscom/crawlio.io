import asyncio

from app.db.base import Base
import app.db.models  # noqa: F401
from app.db.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created OK")


asyncio.run(main())