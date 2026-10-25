from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db, engine
from app.models.base import Base
from app.models import player, team, match, squad, innings, delivery
from app.routers.router import router

from fastapi.responses import JSONResponse
from app.domain.exceptions import CricketDomainError

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Cricbuzz", lifespan=lifespan)

@app.exception_handler(CricketDomainError)
async def domain_exception_handler(request, exc: CricketDomainError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )

app.include_router(router)

@app.get("/")
def root():
    return {"message": "Cricbuzz app is running"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}