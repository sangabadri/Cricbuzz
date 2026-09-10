from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db, engine
from app.models.base import Base
from app.models import player, team, match

Base.metadata.create_all(bind=engine)

from app.routers.router import router

app = FastAPI(title="Cricbuzz")
app.include_router(router)

@app.get("/")
def root():
    return {"message": "Cricbuzz app is running"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}