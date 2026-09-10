from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.player import Player
from app.schemas.player import PlayerCreate, PlayerResponse
from app.services.player import validate_player, get_player as get_player_service

router = APIRouter(prefix = "/players", tags=["Players"])

@router.get("/{player_id}", response_model=PlayerResponse)
def get_player(player_id : int, db : Session = Depends(get_db)):
    return get_player_service(player_id, db)

@router.post("/", response_model=PlayerResponse)
def create_player(player : PlayerCreate, db : Session = Depends(get_db)):
    validate_player(player)
    db_player=Player(name=player.name, role=player.role, batting=player.batting, bowling=player.bowling)
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player