from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.schemas.enums import MatchFormat, MatchStatus, TossDecision

class MatchCreate(BaseModel):
    team_a : int
    team_b : int
    venue : str
    match_date : datetime
    format : MatchFormat
    
class MatchResponse(MatchCreate):
    model_config=ConfigDict(from_attributes=True)
    
    id : int
    status : MatchStatus
    mom : int | None
    winner :int | None
    toss_winner : int | None
    toss_decision : TossDecision | None
    team_a_name : str | None = None
    team_b_name : str | None = None
    winner_name : str | None = None
    
class MatchToss(BaseModel):
    toss_winner : int
    toss_decision : TossDecision

class MatchMOM(BaseModel):
    player_id : int