"""Create all tables (development bootstrap). Prefer Alembic for production."""

import asyncio

from app.db.base import Base
from app.db.session import engine

# Import models so they register with Base.metadata.
from app.models import (  # noqa: F401
    Delivery,
    Innings,
    Match,
    MatchRoster,
    Player,
    Team,
)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(create_tables())
