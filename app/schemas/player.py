from pydantic import BaseModel, ConfigDict
from app.schemas.enums import Role, BattingStyle, BowlingStyle

class PlayerCreate(BaseModel):
    name : str
    role : Role
    batting : BattingStyle
    bowling : BowlingStyle | None = None

class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id : int
    name : str
    role : Role
    batting : BattingStyle
    bowling : BowlingStyle | None = None