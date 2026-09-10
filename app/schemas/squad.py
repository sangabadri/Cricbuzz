from pydantic import BaseModel, ConfigDict

class SquadPlayer(BaseModel):
    player_id : int
    is_playing_xi : bool

class SquadCreate(BaseModel):
    team_id : int
    players : list[SquadPlayer]
    captain_id : int
    wicket_keeper_id : int

class SquadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id : int
    match_id : int
    team_id : int
    players : list[SquadPlayer]
    captain_id : int
    wicket_keeper_id : int