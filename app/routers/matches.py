from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.match import Match
from app.schemas.match import MatchCreate, MatchResponse, MatchToss
from app.schemas.enums import MatchStatus
from app.services.match import validate_match, get_match as get_match_service

router=APIRouter(prefix="/matches", tags=["Matches"])

@router.get("/{match_id}", response_model=MatchResponse)
def get_match(match_id : int, db : Session = Depends(get_db)):
    return get_match_service(match_id, db)

@router.post("/", response_model=MatchResponse)
def create_match(match : MatchCreate, db : Session = Depends(get_db)):
    validate_match(match, db)
    db_match = Match(
        team_a=match.team_a,
        team_b=match.team_b,
        venue=match.venue,
        match_date=match.match_date,
        format=match.format,
        status=MatchStatus.SCHEDULED
    )
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    return db_match


