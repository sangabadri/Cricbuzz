from pydantic import BaseModel, ConfigDict

class TeamCreate(BaseModel):
    name : str
    
class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id : int
    name : str