from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db

from app.models.player import Player
from app.models.squad import Squad, SquadPlayer
from app.schemas.squad import SquadCreate
from app.schemas.enums import Role, MatchStatus
from app.services.util import validate_none, raise_exception
from app.services.match import MatchService

class SquadService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.match_service = MatchService(db)

    def validate_squad_payload(self, squad: SquadCreate):
        if len(squad.players) != 15:
            raise_exception(400, "Squad must contain exactly 15 players")
        player_ids = [sp.player_id for sp in squad.players]
        if len(player_ids) != len(set(player_ids)):
            raise_exception(400, "Squad cannot contain duplicate players")
        xi_count = sum(1 for sp in squad.players if sp.is_playing_xi)
        bench_count = sum(1 for sp in squad.players if not sp.is_playing_xi)
        if xi_count != 11:
            raise_exception(400, "Playing XI must contain exactly 11 players")
        if bench_count != 4:
            raise_exception(400, "Squad must contain exactly 4 bench players")
        xi_player_ids = {sp.player_id for sp in squad.players if sp.is_playing_xi}
        if squad.captain_id not in xi_player_ids:
            raise_exception(400, "Captain must be part of the playing XI")
        if squad.wicket_keeper_id not in xi_player_ids:
            raise_exception(400, "Wicket-keeper must be part of the playing XI")

    def validate_players(self, squad: SquadCreate, players_by_id: dict) -> dict:
        bowler_count = 0
        wicket_keeper_count = 0
        for sp in squad.players:
            if sp.is_playing_xi:
                player = players_by_id[sp.player_id]
                if player.role in (Role.BOWLER, Role.ALLROUNDER):
                    bowler_count += 1
                if player.role == Role.WICKETKEEPER:
                    wicket_keeper_count += 1
        return {
            "bowler_count": bowler_count,
            "wicket_keeper_count": wicket_keeper_count,
        }

    def validate_squad_rules(self, squad: SquadCreate, counts: dict):
        if counts["bowler_count"] < 5:
            raise_exception(400, "Playing XI must contain at least 5 bowlers")
        if counts["wicket_keeper_count"] < 1:
            raise_exception(400, "Playing XI must contain at least one wicket-keeper")

    async def get_squad(self, match_id: int, team_id: int) -> Squad | None:
        match = await self.match_service.get_match(match_id)
        self.match_service.check_match_has_team(match, team_id)
        result = await self.db.execute(
            select(Squad).where(Squad.match_id == match_id, Squad.team_id == team_id)
        )
        return result.scalars().first()

    async def create_squad(self, match_id: int, squad: SquadCreate) -> Squad:
        self.validate_squad_payload(squad)

        match = await self.match_service.get_match(match_id)
        self.match_service.check_match_has_team(match, squad.team_id)

        # Idempotency check: if squad already submitted for this team in this match
        existing_squad = await self.get_squad(match_id, squad.team_id)
        if existing_squad:
            # Check if identical
            existing_pids = await self.db.execute(
                select(SquadPlayer.player_id, SquadPlayer.is_playing_xi)
                .where(SquadPlayer.squad_id == existing_squad.id)
            )
            existing_dict = {r[0]: r[1] for r in existing_pids.all()}
            incoming_dict = {p.player_id: p.is_playing_xi for p in squad.players}
            if (
                existing_dict == incoming_dict
                and existing_squad.captain_id == squad.captain_id
                and existing_squad.wicket_keeper_id == squad.wicket_keeper_id
            ):
                return existing_squad
            raise_exception(400, f"A squad for team {squad.team_id} has already been submitted for this match")

        if match.status != MatchStatus.SCHEDULED:
            raise_exception(400, f"Cannot submit squad for match with status '{match.status.value}'")

        # Check opponent players
        existing_res = await self.db.execute(
            select(SquadPlayer.player_id)
            .join(Squad, Squad.id == SquadPlayer.squad_id)
            .where(Squad.match_id == match_id)
        )
        opponent_player_ids = set(existing_res.scalars().all())
        player_ids = [sp.player_id for sp in squad.players]
        for pid in player_ids:
            if pid in opponent_player_ids:
                raise_exception(400, f"Player {pid} is already part of another squad in this match")

        players_result = await self.db.execute(select(Player).where(Player.id.in_(player_ids)))
        players = players_result.scalars().all()
        players_by_id = {player.id: player for player in players}
        if len(players_by_id) != len(set(player_ids)):
            missing = set(player_ids) - set(players_by_id)
            raise_exception(400, f"Players do not exist: {sorted(missing)}")
        if players_by_id[squad.wicket_keeper_id].role != Role.WICKETKEEPER:
            raise_exception(400, "Designated wicket-keeper must have wicketkeeper role")

        counts = self.validate_players(squad, players_by_id)
        self.validate_squad_rules(squad, counts)

        db_squad = Squad(
            match_id=match_id,
            team_id=squad.team_id,
            captain_id=squad.captain_id,
            wicket_keeper_id=squad.wicket_keeper_id,
        )
        self.db.add(db_squad)
        await self.db.flush()

        for player in squad.players:
            db_player = SquadPlayer(
                squad_id=db_squad.id,
                player_id=player.player_id,
                is_playing_xi=player.is_playing_xi,
            )
            self.db.add(db_player)

        await self.db.commit()
        await self.db.refresh(db_squad)
        return db_squad


# Dependency helper
def get_squad_service(db: AsyncSession = Depends(get_db)) -> SquadService:
    return SquadService(db)

# Backward-compatible function wrappers
async def create_squad(match_id: int, squad: SquadCreate, db: AsyncSession):
    return await SquadService(db).create_squad(match_id, squad)

async def get_squad(match_id: int, team_id: int, db: AsyncSession):
    return await SquadService(db).get_squad(match_id, team_id)

async def validate_squad(match_id: int, squad: SquadCreate, db: AsyncSession):
    # Validates without persisting (used in old procedural flow if needed)
    service = SquadService(db)
    service.validate_squad_payload(squad)
    match = await service.match_service.get_match(match_id)
    service.match_service.check_match_has_team(match, squad.team_id)