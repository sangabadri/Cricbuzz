from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.squad import Squad, SquadPlayer
from app.schemas.squad import SquadCreate, SquadResponse
from app.services.squad import get_squad as get_squad_service, validate_squad
from app.services.util import validate_none

router = APIRouter(prefix="/matches", tags=["Squads"])

@router.get("/{match_id}/squad/{team_id}", response_model=SquadResponse)
def get_squad(match_id : int, team_id : int, db : Session = Depends(get_db)):
    squad = get_squad_service(match_id, team_id, db)
    validate_none(squad, f"Squad for (Match: {match_id}, Team: {team_id})")
    return squad

@router.post("/{match_id}/squad", response_model=SquadResponse)
def  create_squad(match_id : int, squad : SquadCreate, db : Session = Depends(get_db)):
    validate_squad(match_id, squad, db)
    db_squad = Squad(match_id=match_id, team_id=squad.team_id, captain_id=squad.captain_id, wicket_keeper_id=squad.wicket_keeper_id)
    db.add(db_squad)
    db.flush()
    for player in squad.players:
        db_player = SquadPlayer(squad_id=db_squad.id, player_id=player.player_id, is_playing_xi=player.is_playing_xi)
        db.add(db_player)
    db.commit()
    db.refresh(db_squad)
    return db_squad