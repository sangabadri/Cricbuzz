from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.delivery import Delivery
from app.models.enums import (
    LEGAL_BALLS_PER_OVER,
    ExtraType,
    InningsStatus,
    MatchFormat,
    MatchStatus,
    is_legal_delivery_extra,
)
from app.models.innings import Innings
from app.models.match import Match
from app.models.match_roster import MatchRoster
from app.schemas.delivery import (
    DeliveryResponse,
    InningsStateResponse,
    RecordDeliveryRequest,
    RecordDeliveryResponse,
)


async def record_delivery(
    session: AsyncSession,
    innings_id: int,
    payload: RecordDeliveryRequest,
) -> RecordDeliveryResponse:
    innings = await _load_innings_for_update(session, innings_id)
    match = innings.match

    if match.status not in (MatchStatus.LIVE, MatchStatus.SCHEDULED):
        raise ValidationError(f"Cannot record deliveries for match in status '{match.status.value}'")

    if match.status == MatchStatus.SCHEDULED:
        match.status = MatchStatus.LIVE

    if innings.status == InningsStatus.NOT_STARTED:
        innings.status = InningsStatus.IN_PROGRESS
    elif innings.status != InningsStatus.IN_PROGRESS:
        raise ValidationError(
            f"Innings {innings_id} is '{innings.status.value}'; only in-progress innings accept deliveries"
        )

    if innings.is_innings_complete:
        raise ValidationError(f"Innings {innings_id} is already complete")

    await _validate_players_in_xi(session, innings, payload)
    await _validate_delivery_slot(session, innings, payload)
    await _validate_bowler_cap(session, innings, payload)

    is_legal = is_legal_delivery_extra(payload.extra_type)
    legal_ball_in_over = _resolve_legal_ball_in_over(innings, is_legal)

    sequence_number = await _next_sequence_number(session, innings_id)
    ball_runs = payload.runs_off_bat + payload.extra_runs

    delivery = Delivery(
        innings_id=innings_id,
        sequence_number=sequence_number,
        over_number=payload.over_number,
        delivery_in_over=payload.delivery_in_over,
        legal_ball_in_over=legal_ball_in_over,
        is_legal_delivery=is_legal,
        striker_id=payload.striker_id,
        non_striker_id=payload.non_striker_id,
        bowler_id=payload.bowler_id,
        runs_off_bat=payload.runs_off_bat,
        extra_type=payload.extra_type,
        extra_runs=payload.extra_runs,
        wicket_type=payload.wicket_type,
        dismissed_player_id=payload.dismissed_player_id,
        fielder_id=payload.fielder_id,
    )

    session.add(delivery)

    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Duplicate delivery: this over already has a delivery with the same "
            f"delivery_in_over ({payload.delivery_in_over}) for over {payload.over_number}"
        ) from exc

    innings.total_runs += ball_runs
    if payload.extra_runs > 0:
        innings.extras_total += payload.extra_runs

    if is_legal:
        innings.legal_balls_bowled += 1

    innings_ended = False
    match_ended = False
    result_summary: str | None = None

    if payload.wicket_type:
        innings.total_wickets += 1

    innings_ended = _finalize_innings_if_needed(innings, match)

    if innings_ended:
        match_ended, result_summary = await _handle_innings_end(session, innings, match)

    return RecordDeliveryResponse(
        delivery=DeliveryResponse.model_validate(delivery),
        innings=_innings_state(innings),
        match_status=match.status.value,
        match_result_summary=result_summary,
        innings_ended=innings_ended,
        match_ended=match_ended,
    )


async def _load_innings_for_update(session: AsyncSession, innings_id: int) -> Innings:
    result = await session.execute(
        select(Innings)
        .where(Innings.id == innings_id)
        .options(
            selectinload(Innings.match).selectinload(Match.team_a),
            selectinload(Innings.match).selectinload(Match.team_b),
            selectinload(Innings.match).selectinload(Match.innings),
        )
        .with_for_update(of=Innings)
    )
    innings = result.scalar_one_or_none()
    if innings is None:
        raise NotFoundError(f"Innings {innings_id} not found")
    return innings


async def _validate_players_in_xi(
    session: AsyncSession,
    innings: Innings,
    payload: RecordDeliveryRequest,
) -> None:
    player_ids = {
        payload.striker_id,
        payload.non_striker_id,
        payload.bowler_id,
    }
    if payload.dismissed_player_id:
        player_ids.add(payload.dismissed_player_id)
    if payload.fielder_id:
        player_ids.add(payload.fielder_id)

    result = await session.execute(
        select(MatchRoster).where(
            MatchRoster.match_id == innings.match_id,
            MatchRoster.player_id.in_(player_ids),
            MatchRoster.is_playing_xi.is_(True),
        )
    )
    roster_rows = {row.player_id: row for row in result.scalars().all()}

    missing = player_ids - roster_rows.keys()
    if missing:
        raise ValidationError(
            f"Players {sorted(missing)} are not in the playing XI for match {innings.match_id}"
        )

    batting_ids = {payload.striker_id, payload.non_striker_id}
    if payload.dismissed_player_id:
        batting_ids.add(payload.dismissed_player_id)

    for pid in batting_ids:
        row = roster_rows[pid]
        if row.team_id != innings.batting_team_id:
            raise ValidationError(f"Player {pid} is not on the batting team for this innings")

    bowler_row = roster_rows[payload.bowler_id]
    if bowler_row.team_id != innings.bowling_team_id:
        raise ValidationError(
            f"Bowler {payload.bowler_id} is not on the bowling team for this innings"
        )


async def _validate_delivery_slot(
    session: AsyncSession,
    innings: Innings,
    payload: RecordDeliveryRequest,
) -> None:
    expected_over = innings.legal_balls_bowled // LEGAL_BALLS_PER_OVER
    if payload.over_number != expected_over:
        raise ValidationError(
            f"over_number must be {expected_over} (current over), got {payload.over_number}"
        )

    max_delivery = await session.scalar(
        select(func.coalesce(func.max(Delivery.delivery_in_over), 0)).where(
            Delivery.innings_id == innings.id,
            Delivery.over_number == payload.over_number,
        )
    )
    expected_delivery_in_over = (max_delivery or 0) + 1
    if payload.delivery_in_over != expected_delivery_in_over:
        raise ValidationError(
            f"delivery_in_over must be {expected_delivery_in_over} for over "
            f"{payload.over_number}, got {payload.delivery_in_over}"
        )

    duplicate = await session.scalar(
        select(Delivery.id).where(
            Delivery.innings_id == innings.id,
            Delivery.over_number == payload.over_number,
            Delivery.delivery_in_over == payload.delivery_in_over,
        )
    )
    if duplicate is not None:
        raise ConflictError(
            f"Duplicate ball: over {payload.over_number} already has "
            f"delivery_in_over={payload.delivery_in_over}"
        )

    is_legal = is_legal_delivery_extra(payload.extra_type)
    if is_legal and innings.balls_in_current_over >= LEGAL_BALLS_PER_OVER:
        raise ValidationError("This over already has 6 legal deliveries; cannot add another legal ball")


async def _validate_bowler_cap(
    session: AsyncSession,
    innings: Innings,
    payload: RecordDeliveryRequest,
) -> None:
    if innings.max_bowler_overs is None:
        return
    if not is_legal_delivery_extra(payload.extra_type):
        return

    legal_balls = await session.scalar(
        select(func.count())
        .select_from(Delivery)
        .where(
            Delivery.innings_id == innings.id,
            Delivery.bowler_id == payload.bowler_id,
            Delivery.is_legal_delivery.is_(True),
        )
    )
    max_legal_balls = innings.max_bowler_overs * LEGAL_BALLS_PER_OVER
    if (legal_balls or 0) >= max_legal_balls:
        raise ValidationError(
            f"Bowler {payload.bowler_id} has reached the maximum of "
            f"{innings.max_bowler_overs} overs for this format"
        )


def _resolve_legal_ball_in_over(innings: Innings, is_legal: bool) -> int | None:
    if not is_legal:
        return None
    return innings.balls_in_current_over + 1


async def _next_sequence_number(session: AsyncSession, innings_id: int) -> int:
    current = await session.scalar(
        select(func.coalesce(func.max(Delivery.sequence_number), 0)).where(
            Delivery.innings_id == innings_id
        )
    )
    return (current or 0) + 1


def _finalize_innings_if_needed(innings: Innings, match: Match) -> bool:
    if innings.is_innings_complete:
        innings.status = InningsStatus.COMPLETED
        return True

    if innings.innings_number == 2 and innings.target_runs is not None:
        if innings.total_runs >= innings.target_runs:
            innings.status = InningsStatus.COMPLETED
            return True

    return False


async def _handle_innings_end(
    session: AsyncSession,
    innings: Innings,
    match: Match,
) -> tuple[bool, str | None]:
    if innings.innings_number == 1 and match.format != MatchFormat.TEST:
        caps = Innings.caps_from_match_format(match.format)
        second = Innings(
            match_id=match.id,
            innings_number=2,
            batting_team_id=innings.bowling_team_id,
            bowling_team_id=innings.batting_team_id,
            status=InningsStatus.NOT_STARTED,
            target_runs=innings.total_runs + 1,
            **caps,
        )
        session.add(second)
        await session.flush()
        match.innings.append(second)
        return False, None

    match.status = MatchStatus.COMPLETED
    winner_id, summary = _compute_match_result(match, innings)
    match.winner_id = winner_id
    match.result_summary = summary
    return True, summary


def _compute_match_result(match: Match, final_innings: Innings) -> tuple[int | None, str]:
    first_innings = next((i for i in match.innings if i.innings_number == 1), None)
    if first_innings is None:
        return None, "Match completed"

    if final_innings.innings_number == 2:
        chasing_team_id = final_innings.batting_team_id
        target = first_innings.total_runs + 1
        if final_innings.total_runs >= target:
            chasing_name = _team_name(match, chasing_team_id)
            margin = final_innings.total_wickets
            wickets_left = 10 - margin
            return (
                chasing_team_id,
                f"{chasing_name} won by {wickets_left} wicket(s)",
            )
        bowling_team_id = final_innings.bowling_team_id
        bowling_name = _team_name(match, bowling_team_id)
        runs_short = target - final_innings.total_runs
        return (
            bowling_team_id,
            f"{bowling_name} won by {runs_short} run(s)",
        )

    return None, "Match completed"


def _team_name(match: Match, team_id: int) -> str:
    if match.team_a_id == team_id:
        return match.team_a.name
    return match.team_b.name


def _innings_state(innings: Innings) -> InningsStateResponse:
    return InningsStateResponse(
        id=innings.id,
        status=innings.status.value,
        total_runs=innings.total_runs,
        total_wickets=innings.total_wickets,
        legal_balls_bowled=innings.legal_balls_bowled,
        overs_display=innings.overs_display,
        is_innings_complete=innings.is_innings_complete,
        target_runs=innings.target_runs,
    )
