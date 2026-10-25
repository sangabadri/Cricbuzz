from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from collections.abc import AsyncGenerator

DATABASE_URL = (
    f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        yield db