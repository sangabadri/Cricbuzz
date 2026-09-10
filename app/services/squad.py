from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.player import Player
from app.models.squad import Squad, SquadPlayer
from app.schemas.squad import SquadCreate
from app.schemas.enums import Role
from app.services.util import validate_exists
from app.services.match import get_match, check_match_has_team

def get_squad(match_id : int, team_id : int, db : Session):
    match = get_match(match_id, db)
    check_match_has_team(match, team_id)
    squad=(
        db.query(Squad)
        .filter(Squad.match_id==match_id, Squad.team_id==team_id)
        .first()
    )
    return squad

def validate_squad(match_id : int, squad : SquadCreate, db : Session):
    squad_=get_squad(match_id, squad.team_id, db)
    validate_exists(squad_, f"A Squad for (Match: {match_id}, Team: {squad.team_id})")
    opponent_players_ids = {
        sp.player_id
        for sp in (
            db.query(SquadPlayer)
            .join(Squad)
            .filter(Squad.match_id==match_id)
            .all()
        )
    }
    player_ids = [sp.player_id for sp in squad.players]
    players = (
        db.query(Player)
        .filter(Player.id.in_(player_ids))
        .all()
    )
    players_by_id = {
        player.id : player
        for player in players
    }
    if len(players_by_id) != len(set(player_ids)):
        missing = set(player_ids) - set(players_by_id)
        raise HTTPException(status_code=400, detail=f"Players do not exist: {sorted(missing)}")
    counts=validate_players(squad, players_by_id, opponent_players_ids)
    validate_squad_rules(squad, counts)
    
    
def validate_players(squad : SquadCreate, players_by_id : dict, opponent_player_ids : set):
    player_ids = set()
    playing_xi_count = 0
    bench_count = 0
    batsman_count = 0
    bowler_count = 0
    wicket_keeper_count = 0
    captain_found = False
    captain_in_xi = False
    wicket_keeper_found = False
    wicket_keeper_in_xi = False
    for sp in squad.players:
        player_id = sp.player_id
        if player_id in opponent_player_ids:
            raise HTTPException(status_code=400, detail=f"Player {player_id} is already part of another squad in this match")
        if player_id in player_ids:
            raise HTTPException(status_code=400, detail=f"Player {player_id} is already part of the squad")
        player_ids.add(player_id)
        player = players_by_id[player_id]
        if sp.is_playing_xi:
            playing_xi_count += 1
            if player.role == Role.BATSMAN:
                batsman_count += 1
            elif player.role == Role.BOWLER:
                bowler_count += 1
            elif player.role == Role.ALLROUNDER:
                batsman_count += 1
                bowler_count += 1
            elif player.role == Role.WICKETKEEPER:
                wicket_keeper_count += 1
        else:
            bench_count += 1
        if player_id == squad.captain_id:
            captain_found = True
            captain_in_xi = sp.is_playing_xi
        if player_id == squad.wicket_keeper_id:
            wicket_keeper_found = True
            wicket_keeper_in_xi = sp.is_playing_xi
    return {
        "playing_xi_count": playing_xi_count,
        "bench_count": bench_count,
        "batsman_count": batsman_count,
        "bowler_count": bowler_count,
        "wicket_keeper_count": wicket_keeper_count,
        "captain_found": captain_found,
        "captain_in_xi": captain_in_xi,
        "wicket_keeper_found": wicket_keeper_found,
        "wicket_keeper_in_xi": wicket_keeper_in_xi,
    }

def validate_squad_rules(squad: SquadCreate, counts: dict):
    if counts["playing_xi_count"] != 11:
        raise HTTPException(status_code=400, detail="Playing XI must contain exactly 11 players")
    if counts["bench_count"] != 4:
        raise HTTPException(status_code=400, detail="Squad must contain exactly 4 bench players")
    if counts["bowler_count"] < 5:
        raise HTTPException(status_code=400, detail="Playing XI must contain at least 5 bowlers")
    if not counts["captain_found"]:
        raise HTTPException(status_code=400, detail="Captain must be part of the squad")
    if not counts["captain_in_xi"]:
        raise HTTPException(status_code=400, detail="Captain must be part of the playing XI")
    if not counts["wicket_keeper_found"]:
        raise HTTPException(status_code=400, detail="Wicket-keeper must be part of the squad")
    if not counts["wicket_keeper_in_xi"]:
        raise HTTPException(status_code=400, detail="Wicket-keeper must be part of the playing XI")
    if counts["wicket_keeper_count"] != 1:
        raise HTTPException(status_code=400, detail="Playing XI must contain exactly one wicket-keeper")