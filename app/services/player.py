from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.player import Player
from app.schemas.player import PlayerCreate
from app.schemas.enums import Role
from app.services.util import validate_none

def validate_player(player : PlayerCreate):
    if player.role == Role.BATSMAN and player.bowling is not None:
        raise HTTPException(status_code=400, detail="A batsman cannot have a bowling style")
    if player.role == Role.WICKETKEEPER and player.bowling is not None:
        raise HTTPException(status_code=400, detail="A wicket-keeper cannot have a bowling style")
    if player.role == Role.BOWLER and player.bowling is None:
        raise HTTPException(status_code=400, detail="A bowler must have a bowling style")
    if player.role == Role.ALLROUNDER and player.bowling is None:
        raise HTTPException(status_code=400, detail="An all-rounder must have a bowling style")
    
def get_player(player_id : int, db : Session):
    player = db.get(Player, player_id)
    validate_none(player, "Player")
    return player