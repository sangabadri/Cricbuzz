from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.match import Match
from app.models.innings import Innings
from app.models.delivery import Delivery
from app.models.squad import Squad, SquadPlayer
from app.models.player import Player
from app.schemas.enums import ExtraType, WicketType, InningsStatus, MatchStatus
from app.schemas.scorecard import (
    OversRecord,
    DismissalInfo,
    ExtrasBreakdown,
    PlayerSummary,
    BatterScorecard,
    BowlerScorecard,
    FallOfWicket,
    PartnershipBatter,
    Partnership,
    InningsScorecard,
    MatchScorecardResponse,
    LiveCurrentOverBall,
    LiveBatter,
    LiveBowler,
    LiveMatchResponse,
)
from app.services.util import validate_none, raise_exception


def _build_partnership(
    wicket_number: int,
    deliveries: list[Delivery],
    player_names: dict[int, str],
) -> Partnership:
    runs = sum(d.runs + d.extras for d in deliveries)
    legal_balls = sum(1 for d in deliveries if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL))
    overs_record = OversRecord(
        completed_overs=legal_balls // 6,
        balls=legal_balls % 6,
        total_legal_balls=legal_balls,
    )

    batters_seen: list[int] = []
    for d in deliveries:
        if d.batsman_id not in batters_seen:
            batters_seen.append(d.batsman_id)
        if d.non_striker_id not in batters_seen:
            batters_seen.append(d.non_striker_id)

    batters: list[PartnershipBatter] = []
    for pid in batters_seen:
        b_runs = sum(d.runs for d in deliveries if d.batsman_id == pid)
        b_balls = sum(1 for d in deliveries if d.batsman_id == pid and d.extra_type != ExtraType.WIDE)
        batters.append(
            PartnershipBatter(
                player_id=pid,
                player_name=player_names.get(pid, f"Player {pid}"),
                runs=b_runs,
                balls=b_balls,
            )
        )

    return Partnership(
        wicket_number=wicket_number,
        runs=runs,
        balls=legal_balls,
        overs=overs_record,
        batters=batters,
    )


class InningsScorecardCalculator:
    """Encapsulates innings scorecard computation using pure structured numeric records."""

    def __init__(
        self,
        innings: Innings,
        deliveries: list[Delivery],
        squad_rows: list,
        max_overs: int,
    ):
        self.innings = innings
        self.deliveries = deliveries
        self.max_overs = max_overs
        self.player_names = {r.id: r.name for r in squad_rows}
        self.batting_xi = [
            PlayerSummary(id=r.id, name=r.name)
            for r in squad_rows
            if r.team_id == innings.batting_team_id and r.is_playing_xi
        ]

    def calculate_extras(self) -> ExtrasBreakdown:
        wides = sum(d.extras for d in self.deliveries if d.extra_type == ExtraType.WIDE)
        no_balls = sum(d.extras for d in self.deliveries if d.extra_type == ExtraType.NOBALL)
        byes = sum(d.extras for d in self.deliveries if d.extra_type == ExtraType.BYE)
        leg_byes = sum(d.extras for d in self.deliveries if d.extra_type == ExtraType.LEGBYE)
        total = wides + no_balls + byes + leg_byes
        return ExtrasBreakdown(
            byes=byes,
            leg_byes=leg_byes,
            wides=wides,
            no_balls=no_balls,
            total=total,
        )

    def calculate_batting(self) -> list[BatterScorecard]:
        batted_order: list[int] = []
        for d in self.deliveries:
            if d.batsman_id not in batted_order:
                batted_order.append(d.batsman_id)
            if d.non_striker_id not in batted_order:
                batted_order.append(d.non_striker_id)

        batting_list: list[BatterScorecard] = []
        for pid in batted_order:
            batsman_delivs = [d for d in self.deliveries if d.batsman_id == pid]
            b_runs = sum(d.runs for d in batsman_delivs)
            b_balls = sum(1 for d in batsman_delivs if d.extra_type != ExtraType.WIDE)
            fours = sum(1 for d in batsman_delivs if d.runs == 4)
            sixes = sum(1 for d in batsman_delivs if d.runs == 6)
            sr = round((b_runs / b_balls) * 100.0, 2) if b_balls > 0 else None

            out_d = next((d for d in self.deliveries if d.player_out_id == pid), None)
            if out_d is None:
                is_out = False
                dismissal_info = None
            else:
                is_out = True
                b_name = self.player_names.get(out_d.bowler_id, f"Player {out_d.bowler_id}")
                f_name = self.player_names.get(out_d.fielder_id, f"Player {out_d.fielder_id}") if out_d.fielder_id else None
                dismissal_info = DismissalInfo(
                    wicket_type=out_d.wicket_type,
                    bowler_id=out_d.bowler_id,
                    bowler_name=b_name,
                    fielder_id=out_d.fielder_id,
                    fielder_name=f_name,
                )

            batting_list.append(
                BatterScorecard(
                    player_id=pid,
                    player_name=self.player_names.get(pid, f"Player {pid}"),
                    runs=b_runs,
                    balls=b_balls,
                    fours=fours,
                    sixes=sixes,
                    strike_rate=sr,
                    is_out=is_out,
                    dismissal=dismissal_info,
                )
            )

        return batting_list

    def calculate_bowling(self) -> list[BowlerScorecard]:
        bowled_order: list[int] = []
        for d in self.deliveries:
            if d.bowler_id not in bowled_order:
                bowled_order.append(d.bowler_id)

        bowling_list: list[BowlerScorecard] = []
        for bid in bowled_order:
            bowler_delivs = [d for d in self.deliveries if d.bowler_id == bid]
            b_legal = sum(1 for d in bowler_delivs if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL))
            b_overs_record = OversRecord(
                completed_overs=b_legal // 6,
                balls=b_legal % 6,
                total_legal_balls=b_legal,
            )

            bowler_overs = set(d.over for d in bowler_delivs)
            maidens = 0
            for ov in bowler_overs:
                ov_delivs = [d for d in bowler_delivs if d.over == ov]
                ov_legal = sum(1 for d in ov_delivs if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL))
                if ov_legal == 6:
                    ov_runs = sum(d.runs + (d.extras if d.extra_type in (ExtraType.WIDE, ExtraType.NOBALL) else 0) for d in ov_delivs)
                    if ov_runs == 0:
                        maidens += 1

            b_conceded = sum(
                d.runs + (d.extras if d.extra_type in (ExtraType.WIDE, ExtraType.NOBALL) else 0)
                for d in bowler_delivs
            )
            b_wickets = sum(
                1 for d in bowler_delivs
                if d.wicket_type in (
                    WicketType.BOWLED,
                    WicketType.CAUGHT,
                    WicketType.LBW,
                    WicketType.STUMPED,
                    WicketType.HIT_WICKET,
                    WicketType.CAUGHT_AND_BOWLED,
                )
            )
            economy = round(b_conceded / (b_legal / 6.0), 2) if b_legal > 0 else None
            wides_bowled = sum(d.extras for d in bowler_delivs if d.extra_type == ExtraType.WIDE)
            noballs_bowled = sum(d.extras for d in bowler_delivs if d.extra_type == ExtraType.NOBALL)

            bowling_list.append(
                BowlerScorecard(
                    player_id=bid,
                    player_name=self.player_names.get(bid, f"Player {bid}"),
                    overs=b_overs_record,
                    maidens=maidens,
                    runs=b_conceded,
                    wickets=b_wickets,
                    economy=economy,
                    wides=wides_bowled,
                    no_balls=noballs_bowled,
                )
            )
        return bowling_list

    def calculate_fow_and_partnerships(self) -> tuple[list[FallOfWicket], list[Partnership], Partnership | None]:
        fall_of_wickets: list[FallOfWicket] = []
        partnerships: list[Partnership] = []
        current_segment_delivs: list[Delivery] = []
        current_wicket_number = 1
        cumulative_runs = 0
        legal_balls_so_far = 0

        for d in self.deliveries:
            current_segment_delivs.append(d)
            cumulative_runs += d.runs + d.extras
            if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL):
                legal_balls_so_far += 1

            if d.wicket_type is not None:
                fow_overs = OversRecord(
                    completed_overs=legal_balls_so_far // 6,
                    balls=legal_balls_so_far % 6,
                    total_legal_balls=legal_balls_so_far,
                )
                p_out_name = self.player_names.get(d.player_out_id, f"Player {d.player_out_id}")
                fall_of_wickets.append(
                    FallOfWicket(
                        wicket_number=current_wicket_number,
                        player_id=d.player_out_id,
                        player_name=p_out_name,
                        score=cumulative_runs,
                        overs=fow_overs,
                    )
                )
                part = _build_partnership(current_wicket_number, current_segment_delivs, self.player_names)
                partnerships.append(part)
                current_segment_delivs = []
                current_wicket_number += 1

        current_partnership = None
        if current_segment_delivs:
            current_partnership = _build_partnership(
                current_wicket_number,
                current_segment_delivs,
                self.player_names,
            )
            partnerships.append(current_partnership)

        return fall_of_wickets, partnerships, current_partnership

    def build(self) -> InningsScorecard:
        total_runs = sum(d.runs + d.extras for d in self.deliveries)
        legal_balls = sum(1 for d in self.deliveries if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL))
        overs_record = OversRecord(
            completed_overs=legal_balls // 6,
            balls=legal_balls % 6,
            total_legal_balls=legal_balls,
        )
        crr = round(total_runs / (legal_balls / 6.0), 2) if legal_balls > 0 else 0.0

        rrr = None
        if self.innings.target is not None:
            runs_needed = self.innings.target - total_runs
            total_inn_balls = self.max_overs * 6
            balls_remaining = max(0, total_inn_balls - legal_balls)
            if runs_needed <= 0:
                rrr = 0.0
            elif balls_remaining > 0:
                rrr = round(runs_needed / (balls_remaining / 6.0), 2)

        extras = self.calculate_extras()
        batting_list = self.calculate_batting()
        bowling_list = self.calculate_bowling()
        fow, partnerships, _ = self.calculate_fow_and_partnerships()
        wickets = len(fow)

        batting_team_name = (
            self.innings.batting_team_obj.name
            if self.innings.batting_team_obj
            else f"Team {self.innings.batting_team_id}"
        )
        bowling_team_name = (
            self.innings.bowling_team_obj.name
            if self.innings.bowling_team_obj
            else f"Team {self.innings.bowling_team_id}"
        )

        return InningsScorecard(
            innings_number=self.innings.innings_number,
            batting_team_id=self.innings.batting_team_id,
            batting_team_name=batting_team_name,
            bowling_team_id=self.innings.bowling_team_id,
            bowling_team_name=bowling_team_name,
            status=self.innings.status,
            runs=total_runs,
            wickets=wickets,
            overs=overs_record,
            current_run_rate=crr,
            target=self.innings.target,
            required_run_rate=rrr,
            extras=extras,
            batting=batting_list,
            bowling=bowling_list,
            fall_of_wickets=fow,
            partnerships=partnerships,
        )


def build_innings_scorecard(
    innings: Innings,
    deliveries: list[Delivery],
    squad_rows: list,
    max_overs: int,
) -> InningsScorecard:
    return InningsScorecardCalculator(innings, deliveries, squad_rows, max_overs).build()


class ScorecardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_match_scorecard(self, match_id: int) -> MatchScorecardResponse:
        match_res = await self.db.execute(
            select(Match)
            .options(
                selectinload(Match.team_a_obj),
                selectinload(Match.team_b_obj),
                selectinload(Match.toss_winner_obj),
                selectinload(Match.winner_obj),
                selectinload(Match.mom_obj),
                selectinload(Match.innings).selectinload(Innings.batting_team_obj),
                selectinload(Match.innings).selectinload(Innings.bowling_team_obj),
            )
            .where(Match.id == match_id)
        )
        match = match_res.scalar_one_or_none()
        validate_none(match, "Match")

        squad_res = await self.db.execute(
            select(Player.id, Player.name, SquadPlayer.is_playing_xi, Squad.team_id)
            .join(Squad, Squad.id == SquadPlayer.squad_id)
            .join(Player, Player.id == SquadPlayer.player_id)
            .where(Squad.match_id == match_id)
        )
        squad_rows = squad_res.all()

        deliv_res = await self.db.execute(
            select(Delivery)
            .join(Innings, Innings.id == Delivery.innings_id)
            .where(Innings.match_id == match_id)
            .order_by(Delivery.innings_id, Delivery.over, Delivery.ball)
        )
        all_delivs = deliv_res.scalars().all()

        innings_scorecards = []
        for inn in match.innings:
            inn_delivs = [d for d in all_delivs if d.innings_id == inn.id]
            card = build_innings_scorecard(
                innings=inn,
                deliveries=inn_delivs,
                squad_rows=squad_rows,
                max_overs=match.format.max_overs,
            )
            innings_scorecards.append(card)

        mom_name = match.mom_obj.name if match.mom_obj else None

        return MatchScorecardResponse(
            match_id=match.id,
            format=match.format,
            status=match.status,
            venue=match.venue,
            match_date=match.match_date,
            team_a_id=match.team_a,
            team_a_name=match.team_a_obj.name,
            team_b_id=match.team_b,
            team_b_name=match.team_b_obj.name,
            toss_winner_id=match.toss_winner,
            toss_winner_name=match.toss_winner_obj.name if match.toss_winner_obj else None,
            toss_decision=match.toss_decision,
            winner_id=match.winner,
            winner_name=match.winner_obj.name if match.winner_obj else None,
            mom_id=match.mom,
            mom_name=mom_name,
            innings=innings_scorecards,
        )

    async def get_innings_scorecard(self, match_id: int, innings_number: int) -> InningsScorecard:
        scorecard = await self.get_match_scorecard(match_id)
        for inn_card in scorecard.innings:
            if inn_card.innings_number == innings_number:
                return inn_card
        raise_exception(404, f"Innings {innings_number} not found for match {match_id}")

    async def get_live_match_state(self, match_id: int) -> LiveMatchResponse:
        match_res = await self.db.execute(
            select(Match)
            .options(
                selectinload(Match.team_a_obj),
                selectinload(Match.team_b_obj),
                selectinload(Match.winner_obj),
                selectinload(Match.innings).selectinload(Innings.batting_team_obj),
                selectinload(Match.innings).selectinload(Innings.bowling_team_obj),
            )
            .where(Match.id == match_id)
        )
        match = match_res.scalar_one_or_none()
        validate_none(match, "Match")

        active_inn = None
        for inn in match.innings:
            if inn.status == InningsStatus.IN_PROGRESS:
                active_inn = inn
                break
        if not active_inn and match.innings:
            active_inn = match.innings[-1]

        if not active_inn:
            return LiveMatchResponse(
                match_id=match.id,
                status=match.status,
                format=match.format,
                venue=match.venue,
                team_a_name=match.team_a_obj.name,
                team_b_name=match.team_b_obj.name,
            )

        squad_res = await self.db.execute(
            select(Player.id, Player.name, SquadPlayer.is_playing_xi, Squad.team_id)
            .join(Squad, Squad.id == SquadPlayer.squad_id)
            .join(Player, Player.id == SquadPlayer.player_id)
            .where(Squad.match_id == match_id)
        )
        squad_rows = squad_res.all()
        player_names = {r.id: r.name for r in squad_rows}

        deliv_res = await self.db.execute(
            select(Delivery)
            .where(Delivery.innings_id == active_inn.id)
            .order_by(Delivery.over, Delivery.ball)
        )
        deliveries = deliv_res.scalars().all()

        inn_card = build_innings_scorecard(
            innings=active_inn,
            deliveries=deliveries,
            squad_rows=squad_rows,
            max_overs=match.format.max_overs,
        )

        striker: LiveBatter | None = None
        non_striker: LiveBatter | None = None
        current_bowler: LiveBowler | None = None
        current_over_balls: list[LiveCurrentOverBall] = []
        last_event_runs: int | None = None
        last_event_is_wicket: bool = False

        if deliveries:
            last_d = deliveries[-1]
            last_event_runs = last_d.runs + last_d.extras
            last_event_is_wicket = (last_d.wicket_type is not None)

            curr_over = last_d.over
            over_delivs = [d for d in deliveries if d.over == curr_over]
            current_over_balls = [
                LiveCurrentOverBall(
                    ball_number=d.ball,
                    runs=d.runs,
                    extra_type=d.extra_type,
                    extras=d.extras,
                    is_wicket=(d.wicket_type is not None),
                    wicket_type=d.wicket_type,
                )
                for d in over_delivs
            ]

            last_legal = next(
                (d for d in reversed(deliveries) if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL)),
                None,
            )
            is_over_complete = False
            if last_legal:
                over_legal = sum(1 for d in over_delivs if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL))
                is_over_complete = (over_legal == 6)

            st_id = last_d.batsman_id
            ns_id = last_d.non_striker_id

            if last_d.wicket_type is not None:
                if last_d.player_out_id == st_id:
                    st_id = None
                elif last_d.player_out_id == ns_id:
                    ns_id = None

            if not is_over_complete:
                cur_bowl_id = last_d.bowler_id
                b_stat = next((b for b in inn_card.bowling if b.player_id == cur_bowl_id), None)
                if b_stat:
                    current_bowler = LiveBowler(
                        player_id=b_stat.player_id,
                        name=b_stat.player_name,
                        overs=b_stat.overs,
                        maidens=b_stat.maidens,
                        runs=b_stat.runs,
                        wickets=b_stat.wickets,
                        economy=b_stat.economy,
                    )

            if st_id:
                b_stat = next((b for b in inn_card.batting if b.player_id == st_id), None)
                if b_stat:
                    striker = LiveBatter(
                        player_id=b_stat.player_id,
                        name=b_stat.player_name,
                        runs=b_stat.runs,
                        balls=b_stat.balls,
                        fours=b_stat.fours,
                        sixes=b_stat.sixes,
                        strike_rate=b_stat.strike_rate,
                    )

            if ns_id:
                b_stat = next((b for b in inn_card.batting if b.player_id == ns_id), None)
                if b_stat:
                    non_striker = LiveBatter(
                        player_id=b_stat.player_id,
                        name=b_stat.player_name,
                        runs=b_stat.runs,
                        balls=b_stat.balls,
                        fours=b_stat.fours,
                        sixes=b_stat.sixes,
                        strike_rate=b_stat.strike_rate,
                    )

        runs_needed = None
        balls_remaining = None

        if active_inn.target is not None:
            runs_needed = max(0, active_inn.target - inn_card.runs)
            legal_balls = sum(1 for d in deliveries if d.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL))
            total_inn_balls = match.format.max_overs * 6
            balls_remaining = max(0, total_inn_balls - legal_balls)

        return LiveMatchResponse(
            match_id=match.id,
            status=match.status,
            format=match.format,
            venue=match.venue,
            team_a_name=match.team_a_obj.name,
            team_b_name=match.team_b_obj.name,
            current_innings_number=active_inn.innings_number,
            batting_team_name=inn_card.batting_team_name,
            bowling_team_name=inn_card.bowling_team_name,
            runs=inn_card.runs,
            wickets=inn_card.wickets,
            overs=inn_card.overs,
            current_run_rate=inn_card.current_run_rate,
            target=active_inn.target,
            runs_needed=runs_needed,
            balls_remaining=balls_remaining,
            required_run_rate=inn_card.required_run_rate,
            striker=striker,
            non_striker=non_striker,
            current_bowler=current_bowler,
            current_over_balls=current_over_balls,
            last_event_runs=last_event_runs,
            last_event_is_wicket=last_event_is_wicket,
        )


def get_scorecard_service(db: AsyncSession = Depends(get_db)) -> ScorecardService:
    return ScorecardService(db)


async def get_match_scorecard(match_id: int, db: AsyncSession) -> MatchScorecardResponse:
    return await ScorecardService(db).get_match_scorecard(match_id)


async def get_innings_scorecard(match_id: int, innings_number: int, db: AsyncSession) -> InningsScorecard:
    return await ScorecardService(db).get_innings_scorecard(match_id, innings_number)


async def get_live_match_state(match_id: int, db: AsyncSession) -> LiveMatchResponse:
    return await ScorecardService(db).get_live_match_state(match_id)
