from pydantic import BaseModel, ConfigDict

class TeamCreate(BaseModel):
    name : str
    
class TeamResponse(TeamCreate):
    model_config = ConfigDict(from_attributes=True)
    
    id : int

class TeamStatsResponse(BaseModel):
    team_id : int
    name : str
    matches_played : int
    matches_won : int
    matches_lost : int
    matches_abandoned : int
    win_percentage : float