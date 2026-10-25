from pydantic import BaseModel, ConfigDict
from app.schemas.enums import ExtraType, WicketType

class DeliveryCreate(BaseModel):
    over : int
    ball : int
    bowler_id : int
    batsman_id : int
    non_striker_id : int
    runs : int = 0
    extra_type : ExtraType | None = None
    extras : int = 0
    wicket_type : WicketType | None = None
    player_out_id : int | None = None
    fielder_id : int | None = None
    commentary : str | None = None

class DeliveryResponse(DeliveryCreate):
    model_config = ConfigDict(from_attributes=True)
    
    id : int
    innings_id : int