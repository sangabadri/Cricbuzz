from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.schemas.enums import MatchFormat, MatchStatus, TossDecision

class MatchCreate(BaseModel):
    team_a : int
    team_b : int
    venue : str
    match_date : datetime
    format : MatchFormat
    
class MatchResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    
    id : int
    team_a : int
    team_b : int
    venue : str
    format : MatchFormat
    status : MatchStatus
    match_date : datetime
    mom : int | None
    winner :int | None
    toss_winner : int | None
    toss_decision : TossDecision | None
    
class MatchToss(BaseModel):
    toss_winner : int
    toss_decision : TossDecision