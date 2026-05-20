from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError
from app.models.enums import LEGAL_BALLS_PER_OVER, InningsStatus, WicketType
from app.models.innings import Innings
from app.models.match import Match
from app.models.player import Player
from app.models.team import Team
from app.schemas.stats import (
    BatsmanCardEntry,
    BatsmanCardResponse,
    BowlerFiguresEntry,
    BowlerFiguresResponse,
    FallOfWicketEntry,
    HeadToHeadResponse,
    InningsSummaryBlock,
    LiveScorecardResponse,
    MatchSummaryResponse,
    PartnershipEntry,
    PartnershipTrackerResponse,
)
from app.services.stats_queries import (
    FALL_OF_WICKETS_SQL,
    LAST_N_OVERS_SQL,
    PARTNERSHIPS_SQL,
    batsman_aggregates_stmt,
    bowler_aggregates_stmt,
    bowler_maidens_stmt,
    dismissal_label,
    dismissal_stmt,
    economy_rate,
    format_overs,
    head_to_head_stmt,
    run_rate,
    strike_rate,
)


async def get_live_scorecard(
    session: AsyncSession,
    match_id: int,
    innings_number: int | None = None,
) -> LiveScorecardResponse:
    innings = await _resolve_innings(session, match_id, innings_number)
    team_name = await session.scalar(
        select(Team.name).where(Team.id == innings.batting_team_id)
    )

    crr = run_rate(innings.total_runs, innings.legal_balls_bowled)
    rrr: float | None = None
    runs_required: int | None = None
    balls_remaining: int | None = None

    if innings.target_runs is not None and innings.status == InningsStatus.IN_PROGRESS:
        runs_required = max(innings.target_runs - innings.total_runs, 0)
        if innings.max_overs is not None:
            max_balls = innings.max_overs * LEGAL_BALLS_PER_OVER
            balls_remaining = max(max_balls - innings.legal_balls_bowled, 0)
            if balls_remaining > 0 and runs_required > 0:
                rrr = round(
                    runs_required * LEGAL_BALLS_PER_OVER / balls_remaining,
                    2,
                )
            elif runs_required == 0:
                rrr = 0.0

    last5 = await session.execute(
        LAST_N_OVERS_SQL,
        {
            "innings_id": innings.id,
            "balls_per_over": LEGAL_BALLS_PER_OVER,
            "num_overs": 5,
        },
    )
    last5_row = last5.one()
    last5_runs = int(last5_row.runs)
    last5_rr = run_rate(last5_runs, int(last5_row.legal_balls))

    return LiveScorecardResponse(
        match_id=match_id,
        innings_id=innings.id,
        innings_number=innings.innings_number,
        batting_team_id=innings.batting_team_id,
        batting_team_name=team_name or "",
        status=innings.status.value,
        total_runs=innings.total_runs,
        total_wickets=innings.total_wickets,
        overs_display=innings.overs_display,
        legal_balls_bowled=innings.legal_balls_bowled,
        extras_total=innings.extras_total,
        current_run_rate=crr,
        required_run_rate=rrr,
        runs_required=runs_required,
        balls_remaining=balls_remaining,
        target_runs=innings.target_runs,
        last_five_overs_runs=last5_runs,
        last_five_overs_run_rate=last5_rr,
    )


async def get_batsman_card(
    session: AsyncSession,
    innings_id: int,
) -> BatsmanCardResponse:
    await _ensure_innings(session, innings_id)

    batting_rows = (await session.execute(batsman_aggregates_stmt(innings_id))).all()
    dismissal_rows = (await session.execute(dismissal_stmt(innings_id))).all()
    dismissals = {r.dismissed_player_id: r for r in dismissal_rows}

    batsmen: list[BatsmanCardEntry] = []
    for row in batting_rows:
        d = dismissals.get(row.player_id)
        if d:
            dismissal = dismissal_label(
                d.wicket_type,
                d.bowler_name,
                d.fielder_name,
            )
        else:
            dismissal = "not out"

        runs = int(row.runs)
        balls = int(row.balls_faced)
        batsmen.append(
            BatsmanCardEntry(
                player_id=row.player_id,
                player_name=row.player_name,
                runs=runs,
                balls_faced=balls,
                strike_rate=strike_rate(runs, balls),
                fours=int(row.fours),
                sixes=int(row.sixes),
                dismissal=dismissal,
            )
        )

    return BatsmanCardResponse(innings_id=innings_id, batsmen=batsmen)


async def get_bowler_figures(
    session: AsyncSession,
    innings_id: int,
) -> BowlerFiguresResponse:
    await _ensure_innings(session, innings_id)

    bowler_rows = (await session.execute(bowler_aggregates_stmt(innings_id))).all()

    maiden_subq = bowler_maidens_stmt(innings_id)
    maiden_result = await session.execute(
        select(
            maiden_subq.c.bowler_id,
            func.count().label("maidens"),
        )
        .select_from(maiden_subq)
        .group_by(maiden_subq.c.bowler_id)
    )
    maiden_map = {r.bowler_id: int(r.maidens) for r in maiden_result.all()}

    bowlers: list[BowlerFiguresEntry] = []
    for row in bowler_rows:
        legal = int(row.legal_balls)
        runs = int(row.runs_conceded)
        bowlers.append(
            BowlerFiguresEntry(
                player_id=row.player_id,
                player_name=row.player_name,
                overs_display=format_overs(legal),
                legal_balls_bowled=legal,
                maidens=maiden_map.get(row.player_id, 0),
                runs_conceded=runs,
                wickets=int(row.wickets),
                economy_rate=economy_rate(runs, legal),
            )
        )

    return BowlerFiguresResponse(innings_id=innings_id, bowlers=bowlers)


async def get_partnership_tracker(
    session: AsyncSession,
    innings_id: int,
) -> PartnershipTrackerResponse:
    await _ensure_innings(session, innings_id)

    result = await session.execute(
        PARTNERSHIPS_SQL,
        {"innings_id": innings_id},
    )
    rows = result.all()
    if not rows:
        return PartnershipTrackerResponse(
            innings_id=innings_id,
            current_partnership=None,
            past_partnerships=[],
        )

    player_ids: set[int] = set()
    for row in rows:
        player_ids.add(row.batsman_1_id)
        player_ids.add(row.batsman_2_id)

    names_result = await session.execute(
        select(Player.id, Player.name).where(Player.id.in_(player_ids))
    )
    name_map = {r.id: r.name for r in names_result.all()}

    max_partnership = max(r.partnership_no for r in rows)
    entries: list[PartnershipEntry] = []
    for row in rows:
        entries.append(
            PartnershipEntry(
                partnership_number=int(row.partnership_no),
                batsman_1_id=row.batsman_1_id,
                batsman_1_name=name_map.get(row.batsman_1_id, ""),
                batsman_2_id=row.batsman_2_id,
                batsman_2_name=name_map.get(row.batsman_2_id, ""),
                runs=int(row.runs),
                balls_faced=int(row.balls),
                is_current=int(row.partnership_no) == max_partnership,
            )
        )

    current = next((e for e in entries if e.is_current), None)
    past = [e for e in entries if not e.is_current]

    return PartnershipTrackerResponse(
        innings_id=innings_id,
        current_partnership=current,
        past_partnerships=past,
    )


async def get_match_summary(
    session: AsyncSession,
    match_id: int,
) -> MatchSummaryResponse:
    result = await session.execute(
        select(Match)
        .where(Match.id == match_id)
        .options(
            selectinload(Match.team_a),
            selectinload(Match.team_b),
            selectinload(Match.player_of_match),
            selectinload(Match.innings).selectinload(Innings.batting_team),
        )
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise NotFoundError(f"Match {match_id} not found")

    innings_blocks: list[InningsSummaryBlock] = []
    fall_of_wickets: list[FallOfWicketEntry] = []

    for inn in sorted(match.innings, key=lambda i: i.innings_number):
        innings_blocks.append(
            InningsSummaryBlock(
                innings_number=inn.innings_number,
                batting_team_name=inn.batting_team.name,
                total_runs=inn.total_runs,
                total_wickets=inn.total_wickets,
                overs_display=inn.overs_display,
                status=inn.status.value,
            )
        )
        fall_of_wickets.extend(await _fall_of_wickets_for_innings(session, inn.id))

    winner_name: str | None = None
    if match.winner_id == match.team_a_id:
        winner_name = match.team_a.name
    elif match.winner_id == match.team_b_id:
        winner_name = match.team_b.name

    return MatchSummaryResponse(
        match_id=match.id,
        venue=match.venue,
        match_date=match.match_date,
        format=match.format,
        status=match.status,
        team_a_name=match.team_a.name,
        team_b_name=match.team_b.name,
        winner_name=winner_name,
        result_summary=match.result_summary,
        player_of_match_id=match.player_of_match_id,
        player_of_match_name=(
            match.player_of_match.name if match.player_of_match else None
        ),
        innings=innings_blocks,
        fall_of_wickets=sorted(fall_of_wickets, key=lambda f: f.sequence_number),
    )


async def get_head_to_head(
    session: AsyncSession,
    team_a_id: int,
    team_b_id: int,
) -> HeadToHeadResponse:
    if team_a_id == team_b_id:
        raise ValidationError("team_a_id and team_b_id must be different")

    teams = await session.execute(
        select(Team).where(Team.id.in_([team_a_id, team_b_id]))
    )
    team_map = {t.id: t for t in teams.scalars().all()}
    if team_a_id not in team_map or team_b_id not in team_map:
        missing = {team_a_id, team_b_id} - team_map.keys()
        raise NotFoundError(f"Teams not found: {sorted(missing)}")

    row = (await session.execute(head_to_head_stmt(team_a_id, team_b_id))).one()

    return HeadToHeadResponse(
        team_a_id=team_a_id,
        team_a_name=team_map[team_a_id].name,
        team_b_id=team_b_id,
        team_b_name=team_map[team_b_id].name,
        team_a_wins=int(row.team_a_wins or 0),
        team_b_wins=int(row.team_b_wins or 0),
        draws_or_no_result=int(row.draws_or_no_result or 0),
        total_matches=int(row.total_matches or 0),
    )


async def _fall_of_wickets_for_innings(
    session: AsyncSession,
    innings_id: int,
) -> list[FallOfWicketEntry]:
    result = await session.execute(
        FALL_OF_WICKETS_SQL,
        {"innings_id": innings_id},
    )
    rows = result.all()
    if not rows:
        return []

    player_ids = {r.dismissed_player_id for r in rows}
    dismissals_detail = await session.execute(dismissal_stmt(innings_id))
    detail_map = {d.dismissed_player_id: d for d in dismissals_detail.all()}

    names = await session.execute(
        select(Player.id, Player.name).where(Player.id.in_(player_ids))
    )
    name_map = {r.id: r.name for r in names.all()}

    entries: list[FallOfWicketEntry] = []
    for row in rows:
        legal_balls_before = int(row.legal_balls_at_fall)
        detail = detail_map.get(row.dismissed_player_id)
        wt = WicketType(row.wicket_type) if row.wicket_type else None
        entries.append(
            FallOfWicketEntry(
                wicket_number=int(row.wicket_number),
                runs_at_fall=int(row.runs_at_fall),
                overs_at_fall=format_overs(legal_balls_before),
                dismissed_player_id=row.dismissed_player_id,
                dismissed_player_name=name_map.get(row.dismissed_player_id, ""),
                dismissal=disposal_label_from_detail(detail, wt),
                sequence_number=int(row.sequence_number),
            )
        )
    return entries


def disposal_label_from_detail(detail, wicket_type: WicketType | None) -> str:
    if detail is None:
        return wicket_type.value if wicket_type else "out"
    return dismissal_label(
        detail.wicket_type,
        detail.bowler_name,
        detail.fielder_name,
    )


async def _resolve_innings(
    session: AsyncSession,
    match_id: int,
    innings_number: int | None,
) -> Innings:
    if innings_number is not None:
        result = await session.execute(
            select(Innings).where(
                Innings.match_id == match_id,
                Innings.innings_number == innings_number,
            )
        )
        innings = result.scalar_one_or_none()
        if innings is None:
            raise NotFoundError(
                f"Innings {innings_number} not found for match {match_id}"
            )
        return innings

    # Default: latest in-progress, else latest by innings_number
    result = await session.execute(
        select(Innings)
        .where(Innings.match_id == match_id)
        .order_by(
            case(
                (Innings.status == InningsStatus.IN_PROGRESS, 0),
                else_=1,
            ),
            Innings.innings_number.desc(),
        )
        .limit(1)
    )
    innings = result.scalar_one_or_none()
    if innings is None:
        raise NotFoundError(f"No innings found for match {match_id}")
    return innings


async def _ensure_innings(session: AsyncSession, innings_id: int) -> Innings:
    result = await session.execute(
        select(Innings).where(Innings.id == innings_id)
    )
    innings = result.scalar_one_or_none()
    if innings is None:
        raise NotFoundError(f"Innings {innings_id} not found")
    return innings
