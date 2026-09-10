from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.team import TeamCreate, TeamResponse
from app.models.team import Team
from app.services.team import get_team as get_team_service

router=APIRouter(prefix="/team", tags=["Teams"])

@router.get("/{team_id}", response_model=TeamResponse)
def get_team(team_id : int, db : Session = Depends(get_db)):
    return get_team_service(team_id, db)

@router.post("/", response_model=TeamResponse)
def create_team(team : TeamCreate, db : Session = Depends(get_db)):
    db_team = Team(name=team.name)
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team