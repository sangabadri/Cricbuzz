from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db

from app.models.player import Player
from app.models.delivery import Delivery
from app.models.squad import SquadPlayer, Squad
from app.schemas.enums import Role, ExtraType, WicketType
from app.schemas.player import (
    PlayerCreate,
    PlayerCareerStatsResponse,
    PlayerCareerBattingStats,
    PlayerCareerBowlingStats,
    PlayerCareerFieldingStats,
)
from app.schemas.scorecard import OversRecord, BestBowling, HighestScore
from app.services.util import validate_none, validate_exists

class PlayerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_player(self, player_id: int) -> Player:
        player = await self.db.get(Player, player_id)
        validate_none(player, "Player")
        return player

    async def create_player(self, player_in: PlayerCreate) -> Player:
        res = await self.db.execute(select(Player).where(Player.name == player_in.name))
        existing_player = res.scalar_one_or_none()
        validate_exists(existing_player, f"Player with name {player_in.name}")

        db_player = Player(
            name=player_in.name,
            role=player_in.role,
            batting=player_in.batting,
            bowling=player_in.bowling,
        )
        self.db.add(db_player)
        await self.db.commit()
        await self.db.refresh(db_player)
        return db_player

    async def list_players(
        self,
        role: Role | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Player]:
        query = select(Player)
        if role is not None:
            query = query.where(Player.role == role)
        if search:
            query = query.where(Player.name.ilike(f"%{search}%"))
        query = query.order_by(Player.name).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_player_career_stats(self, player_id: int) -> PlayerCareerStatsResponse:
        player = await self.get_player(player_id)

        # 1. Matches played (count matches where player was in Playing XI)
        matches_res = await self.db.execute(
            select(Squad.match_id)
            .join(SquadPlayer, Squad.id == SquadPlayer.squad_id)
            .where(SquadPlayer.player_id == player_id, SquadPlayer.is_playing_xi == True)
            .distinct()
        )
        matches_played = len(matches_res.scalars().all())

        # 2. Batting stats
        bat_deliv_res = await self.db.execute(
            select(Delivery)
            .where((Delivery.batsman_id == player_id) | (Delivery.non_striker_id == player_id))
            .order_by(Delivery.innings_id, Delivery.over, Delivery.ball)
        )
        all_bat_delivs = bat_deliv_res.scalars().all()

        bat_inn_ids = sorted(list(set(
            d.innings_id for d in all_bat_delivs if d.batsman_id == player_id
        )))
        innings_batted = len(bat_inn_ids)

        total_runs = 0
        total_balls = 0
        fours = 0
        sixes = 0
        fifties = 0
        hundreds = 0
        max_score = 0
        max_score_is_not_out = False
        not_outs = 0

        for inn_id in bat_inn_ids:
            inn_delivs = [d for d in all_bat_delivs if d.innings_id == inn_id]
            inn_runs = sum(d.runs for d in inn_delivs if d.batsman_id == player_id)
            inn_balls = sum(1 for d in inn_delivs if d.batsman_id == player_id and d.extra_type != ExtraType.WIDE)
            inn_fours = sum(1 for d in inn_delivs if d.batsman_id == player_id and d.runs == 4)
            inn_sixes = sum(1 for d in inn_delivs if d.batsman_id == player_id and d.runs == 6)

            inn_out = any(d.player_out_id == player_id for d in inn_delivs)
            if not inn_out:
                not_outs += 1

            total_runs += inn_runs
            total_balls += inn_balls
            fours += inn_fours
            sixes += inn_sixes

            if inn_runs >= 100:
                hundreds += 1
            elif inn_runs >= 50:
                fifties += 1

            if inn_runs > max_score:
                max_score = inn_runs
                max_score_is_not_out = (not inn_out)
            elif inn_runs == max_score and not inn_out:
                max_score_is_not_out = True

        dismissals = innings_batted - not_outs
        batting_avg = round(total_runs / dismissals, 2) if dismissals > 0 else (float(total_runs) if total_runs > 0 and innings_batted > 0 else None)
        strike_rate = round((total_runs / total_balls) * 100.0, 2) if total_balls > 0 else None
        highest_score_obj = HighestScore(runs=max_score, is_not_out=max_score_is_not_out) if innings_batted > 0 else None

        batting_stats = PlayerCareerBattingStats(
            matches=matches_played,
            innings=innings_batted,
            not_outs=not_outs,
            runs=total_runs,
            balls=total_balls,
            highest_score=highest_score_obj,
            average=batting_avg,
            strike_rate=strike_rate,
            fifties=fifties,
            hundreds=hundreds,
            fours=fours,
            sixes=sixes,
        )

        # 3. Bowling stats
        bowl_deliv_res = await self.db.execute(
            select(Delivery)
            .where(Delivery.bowler_id == player_id)
            .order_by(Delivery.innings_id, Delivery.over, Delivery.ball)
        )
        all_bowl_delivs = bowl_deliv_res.scalars().all()

        bowl_inn_ids = sorted(list(set(d.innings_id for d in all_bowl_delivs)))
        innings_bowled = len(bowl_inn_ids)
        career_legal_balls = 0
        career_runs_conceded = 0
        career_wickets = 0
        career_maidens = 0
        four_wickets = 0
        five_wickets = 0
        best_wkts = -1
        best_runs = 999999

        for inn_id in bowl_inn_ids:
            inn_delivs = [d for d in all_bowl_delivs if d.innings_id == inn_id]
            inn_legal = sum(1 for d in inn_delivs if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL))
            inn_runs = sum(d.runs + (d.extras if d.extra_type in (ExtraType.WIDE, ExtraType.NOBALL) else 0) for d in inn_delivs)
            inn_wkts = sum(
                1 for d in inn_delivs
                if d.wicket_type in (
                    WicketType.BOWLED,
                    WicketType.CAUGHT,
                    WicketType.LBW,
                    WicketType.STUMPED,
                    WicketType.HIT_WICKET,
                    WicketType.CAUGHT_AND_BOWLED,
                )
            )

            career_legal_balls += inn_legal
            career_runs_conceded += inn_runs
            career_wickets += inn_wkts

            if inn_wkts == 4:
                four_wickets += 1
            elif inn_wkts >= 5:
                five_wickets += 1

            if inn_wkts > best_wkts or (inn_wkts == best_wkts and inn_runs < best_runs):
                best_wkts = inn_wkts
                best_runs = inn_runs

            overs_in_inn = set(d.over for d in inn_delivs)
            for ov in overs_in_inn:
                ov_delivs = [d for d in inn_delivs if d.over == ov]
                ov_legal = sum(1 for d in ov_delivs if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL))
                if ov_legal == 6:
                    ov_runs = sum(d.runs + (d.extras if d.extra_type in (ExtraType.WIDE, ExtraType.NOBALL) else 0) for d in ov_delivs)
                    if ov_runs == 0:
                        career_maidens += 1

        overs_record = OversRecord(
            completed_overs=career_legal_balls // 6,
            balls=career_legal_balls % 6,
            total_legal_balls=career_legal_balls,
        )
        bowling_avg = round(career_runs_conceded / career_wickets, 2) if career_wickets > 0 else None
        economy = round(career_runs_conceded / (career_legal_balls / 6.0), 2) if career_legal_balls > 0 else None
        best_bowling_obj = BestBowling(wickets=best_wkts, runs=best_runs) if (best_wkts >= 0 and innings_bowled > 0) else None

        bowling_stats = PlayerCareerBowlingStats(
            innings=innings_bowled,
            balls=career_legal_balls,
            overs=overs_record,
            maidens=career_maidens,
            runs_conceded=career_runs_conceded,
            wickets=career_wickets,
            average=bowling_avg,
            economy=economy,
            best_bowling=best_bowling_obj,
            four_wickets=four_wickets,
            five_wickets=five_wickets,
        )

        # 4. Fielding stats
        field_res = await self.db.execute(
            select(Delivery.wicket_type)
            .where(Delivery.fielder_id == player_id)
        )
        field_wickets = field_res.scalars().all()
        catches = sum(1 for w in field_wickets if w == WicketType.CAUGHT)
        stumpings = sum(1 for w in field_wickets if w == WicketType.STUMPED)
        run_outs = sum(1 for w in field_wickets if w == WicketType.RUN_OUT)

        fielding_stats = PlayerCareerFieldingStats(
            catches=catches,
            stumpings=stumpings,
            run_outs=run_outs,
        )

        return PlayerCareerStatsResponse(
            player_id=player.id,
            name=player.name,
            role=player.role,
            batting_style=player.batting,
            bowling_style=player.bowling,
            batting=batting_stats,
            bowling=bowling_stats,
            fielding=fielding_stats,
        )


# Dependency helper
def get_player_service(db: AsyncSession = Depends(get_db)) -> PlayerService:
    return PlayerService(db)

# Backward-compatible function wrappers
def validate_player(player_in: PlayerCreate):
    pass

async def create_player(player_in: PlayerCreate, db: AsyncSession) -> Player:
    return await PlayerService(db).create_player(player_in)

async def get_player(player_id: int, db: AsyncSession) -> Player:
    return await PlayerService(db).get_player(player_id)

async def list_players(role: Role | None, search: str | None, db: AsyncSession, limit: int = 20, offset: int = 0):
    return await PlayerService(db).list_players(role=role, search=search, limit=limit, offset=offset)

async def get_player_career_stats(player_id: int, db: AsyncSession) -> PlayerCareerStatsResponse:
    return await PlayerService(db).get_player_career_stats(player_id)