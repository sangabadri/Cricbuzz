import asyncio
import os
import sys
import pytest
from collections.abc import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "cricbuzz_test"

from app.config import settings
from app.database import get_db
from app.models.base import Base
from app.models import player, team, match, squad, innings, delivery  # Register all models
from app.main import app

TEST_DATABASE_URL = (
    f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False
)

@pytest.fixture(autouse=True)
async def clean_database(request):
    """Drops and recreates schema public before each DB test function."""
    if "unit" in str(request.node.fspath):
        yield
        return
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session

@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
