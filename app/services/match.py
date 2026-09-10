from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.match import Match
from app.schemas.match import MatchCreate, MatchToss
from app.models.team import Team
from app.schemas.enums import MatchStatus, TossDecision
from app.services.util import validate_none

IST = ZoneInfo("Asia/Kolkata")

def validate_match(match : MatchCreate, db : Session):
    team_a = db.get(Team, match.team_a)
    validate_none(team_a, "Team A")
    team_b = db.get(Team, match.team_b)
    validate_none(team_b, "Team B")
    if match.team_a == match.team_b:
        raise HTTPException(status_code=400, detail="Both teams cannot be same")
    if match.match_date <= datetime.now(IST):
        raise HTTPException(status_code=400, detail="Cannot create a match in the past")
    
def check_match_has_team(match : Match, team_id : int):
    if match.team_a!=team_id and match.team_b!=team_id:
        raise HTTPException(status_code=404, detail=f"Match {match.id} doesn't have team {team_id}")

def get_match(match_id : int, db : Session):
    match=db.get(Match, match_id)
    validate_none(match, "Match")
    return match