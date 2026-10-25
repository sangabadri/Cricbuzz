from pydantic import BaseModel, ConfigDict
from app.schemas.enums import InningsStatus

class InningsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id : int
    match_id : int
    innings_number : int
    batting_team_id : int
    bowling_team_id : int
    status : InningsStatus
    target : int | None = None