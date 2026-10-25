from pydantic import BaseModel, ConfigDict
from app.schemas.enums import Role, BattingStyle, BowlingStyle

class PlayerCreate(BaseModel):
    name : str
    role : Role
    batting : BattingStyle
    bowling : BowlingStyle | None = None

class PlayerResponse(PlayerCreate):
    model_config = ConfigDict(from_attributes=True)
    
    id : int

from app.schemas.scorecard import OversRecord, BestBowling, HighestScore

class PlayerCareerBattingStats(BaseModel):
    matches : int
    innings : int
    not_outs : int
    runs : int
    balls : int
    highest_score : HighestScore | None = None
    average : float | None = None
    strike_rate : float | None = None
    fifties : int
    hundreds : int
    fours : int
    sixes : int

class PlayerCareerBowlingStats(BaseModel):
    innings : int
    balls : int
    overs : OversRecord
    maidens : int
    runs_conceded : int
    wickets : int
    average : float | None = None
    economy : float | None = None
    best_bowling : BestBowling | None = None
    four_wickets : int
    five_wickets : int

class PlayerCareerFieldingStats(BaseModel):
    catches : int
    stumpings : int
    run_outs : int

class PlayerCareerStatsResponse(BaseModel):
    player_id : int
    name : str
    role : Role
    batting_style : BattingStyle
    bowling_style : BowlingStyle | None
    batting : PlayerCareerBattingStats
    bowling : PlayerCareerBowlingStats
    fielding : PlayerCareerFieldingStats