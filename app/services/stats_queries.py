"""
Reusable SQL fragments and aggregation helpers for read-heavy scorecard paths.
Uses denormalized innings counters where possible; aggregates deliveries in SQL.
"""

from __future__ import annotations

from sqlalchemy import and_, case, func, select, text
from sqlalchemy.sql import ColumnElement

from app.models.delivery import Delivery
from app.models.enums import LEGAL_BALLS_PER_OVER, ExtraType, WicketType

# Runs charged to the bowler (excludes byes and leg-byes).
BOWLER_RUNS_EXPR: ColumnElement[int] = (
    Delivery.runs_off_bat
    + case(
        (Delivery.extra_type.in_([ExtraType.BYE, ExtraType.LEG_BYE]), 0),
        else_=Delivery.extra_runs,
    )
)

# Balls faced by striker: legal deliveries + no-balls (batsman always faces NB).
BALLS_FACED_EXPR: ColumnElement[int] = case(
    (
        Delivery.is_legal_delivery.is_(True),
        1,
    ),
    (
        Delivery.extra_type == ExtraType.NO_BALL,
        1,
    ),
    else_=0,
)

BOWLING_WICKET_TYPES = (
    WicketType.BOWLED,
    WicketType.CAUGHT,
    WicketType.LBW,
    WicketType.STUMPED,
    WicketType.HIT_WICKET,
    WicketType.CAUGHT_AND_BOWLED,
)


def overs_decimal(legal_balls: int) -> float:
    return legal_balls / LEGAL_BALLS_PER_OVER


def format_overs(legal_balls: int) -> str:
    completed = legal_balls // LEGAL_BALLS_PER_OVER
    balls = legal_balls % LEGAL_BALLS_PER_OVER
    return f"{completed}.{balls}"


def run_rate(runs: int, legal_balls: int) -> float | None:
    if legal_balls == 0:
        return None
    return round(runs * LEGAL_BALLS_PER_OVER / legal_balls, 2)


def economy_rate(runs: int, legal_balls: int) -> float | None:
    if legal_balls == 0:
        return None
    return round(runs * LEGAL_BALLS_PER_OVER / legal_balls, 2)


def strike_rate(runs: int, balls: int) -> float | None:
    if balls == 0:
        return None
    return round(runs * 100 / balls, 2)


def dismissal_label(
    wicket_type: WicketType | None,
    bowler_name: str | None,
    fielder_name: str | None,
) -> str:
    if wicket_type is None:
        return "not out"
    match wicket_type:
        case WicketType.BOWLED:
            return f"b {bowler_name}" if bowler_name else "bowled"
        case WicketType.CAUGHT:
            if fielder_name and bowler_name:
                return f"c {fielder_name} b {bowler_name}"
            return "caught"
        case WicketType.CAUGHT_AND_BOWLED:
            return f"c & b {bowler_name}" if bowler_name else "caught & bowled"
        case WicketType.LBW:
            return f"lbw b {bowler_name}" if bowler_name else "lbw"
        case WicketType.RUN_OUT:
            return f"run out ({fielder_name})" if fielder_name else "run out"
        case WicketType.STUMPED:
            return f"st {fielder_name} b {bowler_name}" if fielder_name and bowler_name else "stumped"
        case _:
            return wicket_type.value.replace("_", " ")


# Last N completed overs: sum runs where over_number >= current_over - N
LAST_N_OVERS_SQL = text("""
    SELECT COALESCE(SUM(d.runs_off_bat + d.extra_runs), 0)::int AS runs,
           COALESCE(SUM(CASE WHEN d.is_legal_delivery THEN 1 ELSE 0 END), 0)::int AS legal_balls
    FROM deliveries d
    WHERE d.innings_id = :innings_id
      AND d.over_number >= GREATEST(
            (SELECT i.legal_balls_bowled / :balls_per_over FROM innings i WHERE i.id = :innings_id) - :num_overs,
            0
          )
""")


PARTNERSHIPS_SQL = text("""
    WITH balls AS (
        SELECT
            d.sequence_number,
            d.striker_id,
            d.non_striker_id,
            d.runs_off_bat + d.extra_runs AS runs,
            CASE
                WHEN d.is_legal_delivery THEN 1
                WHEN d.extra_type = 'no_ball' THEN 1
                ELSE 0
            END AS legal_ball,
            SUM(CASE WHEN d.wicket_type IS NOT NULL THEN 1 ELSE 0 END)
                OVER (ORDER BY d.sequence_number ROWS UNBOUNDED PRECEDING) AS partnership_no
        FROM deliveries d
        WHERE d.innings_id = :innings_id
    ),
    segments AS (
        SELECT
            partnership_no,
            (ARRAY_AGG(striker_id ORDER BY sequence_number))[1] AS s1,
            (ARRAY_AGG(non_striker_id ORDER BY sequence_number))[1] AS s2,
            SUM(runs)::int AS runs,
            SUM(legal_ball)::int AS balls
        FROM balls
        GROUP BY partnership_no
    )
    SELECT
        partnership_no,
        LEAST(s1, s2) AS batsman_1_id,
        GREATEST(s1, s2) AS batsman_2_id,
        runs,
        balls
    FROM segments
    ORDER BY partnership_no
""")


FALL_OF_WICKETS_SQL = text("""
    WITH wicket_balls AS (
        SELECT
            d.sequence_number,
            d.dismissed_player_id,
            d.wicket_type::text AS wicket_type,
            SUM(d.runs_off_bat + d.extra_runs) OVER (
                ORDER BY d.sequence_number
                ROWS UNBOUNDED PRECEDING
            ) AS runs_at_fall,
            SUM(CASE WHEN d.is_legal_delivery THEN 1 ELSE 0 END) OVER (
                ORDER BY d.sequence_number
                ROWS UNBOUNDED PRECEDING
            ) AS legal_balls_at_fall,
            ROW_NUMBER() OVER (ORDER BY d.sequence_number) AS wicket_number
        FROM deliveries d
        WHERE d.innings_id = :innings_id
          AND d.wicket_type IS NOT NULL
    )
    SELECT
        wicket_number,
        runs_at_fall,
        legal_balls_at_fall,
        dismissed_player_id,
        wicket_type,
        sequence_number
    FROM wicket_balls
    ORDER BY sequence_number
""")


def batsman_aggregates_stmt(innings_id: int):
    """Single grouped query for all batsmen who have faced a ball in the innings."""
    from app.models.player import Player

    return (
        select(
            Delivery.striker_id.label("player_id"),
            Player.name.label("player_name"),
            func.coalesce(func.sum(Delivery.runs_off_bat), 0).label("runs"),
            func.coalesce(func.sum(BALLS_FACED_EXPR), 0).label("balls_faced"),
            func.coalesce(
                func.sum(case((Delivery.runs_off_bat == 4, 1), else_=0)),
                0,
            ).label("fours"),
            func.coalesce(
                func.sum(case((Delivery.runs_off_bat == 6, 1), else_=0)),
                0,
            ).label("sixes"),
        )
        .join(Player, Player.id == Delivery.striker_id)
        .where(Delivery.innings_id == innings_id)
        .group_by(Delivery.striker_id, Player.name)
        .order_by(func.sum(Delivery.runs_off_bat).desc())
    )


def dismissal_stmt(innings_id: int):
    """Latest dismissal per dismissed player (one row per player)."""
    from app.models.player import Player

    bowler = Player.__table__.alias("bowler_p")
    fielder = Player.__table__.alias("fielder_p")

    ranked = (
        select(
            Delivery.dismissed_player_id,
            Delivery.wicket_type,
            bowler.c.name.label("bowler_name"),
            fielder.c.name.label("fielder_name"),
            func.row_number()
            .over(
                partition_by=Delivery.dismissed_player_id,
                order_by=Delivery.sequence_number.desc(),
            )
            .label("rn"),
        )
        .select_from(Delivery)
        .outerjoin(bowler, bowler.c.id == Delivery.bowler_id)
        .outerjoin(fielder, fielder.c.id == Delivery.fielder_id)
        .where(
            Delivery.innings_id == innings_id,
            Delivery.dismissed_player_id.isnot(None),
        )
        .subquery("ranked_dismissals")
    )

    return select(
        ranked.c.dismissed_player_id,
        ranked.c.wicket_type,
        ranked.c.bowler_name,
        ranked.c.fielder_name,
    ).where(ranked.c.rn == 1)


def bowler_aggregates_stmt(innings_id: int):
    from app.models.player import Player

    legal_balls = func.coalesce(
        func.sum(case((Delivery.is_legal_delivery.is_(True), 1), else_=0)),
        0,
    )
    wickets = func.coalesce(
        func.sum(
            case(
                (Delivery.wicket_type.in_(BOWLING_WICKET_TYPES), 1),
                else_=0,
            )
        ),
        0,
    )

    return (
        select(
            Delivery.bowler_id.label("player_id"),
            Player.name.label("player_name"),
            legal_balls.label("legal_balls"),
            func.coalesce(func.sum(BOWLER_RUNS_EXPR), 0).label("runs_conceded"),
            wickets.label("wickets"),
        )
        .join(Player, Player.id == Delivery.bowler_id)
        .where(Delivery.innings_id == innings_id)
        .group_by(Delivery.bowler_id, Player.name)
        .order_by(legal_balls.desc())
    )


def bowler_maidens_stmt(innings_id: int):
    """Completed 6-ball overs with zero runs charged to the bowler."""
    over_runs = func.sum(BOWLER_RUNS_EXPR)
    legal_in_over = func.sum(
        case((Delivery.is_legal_delivery.is_(True), 1), else_=0)
    )
    return (
        select(
            Delivery.bowler_id.label("bowler_id"),
            func.count().label("maidens"),
        )
        .where(
            Delivery.innings_id == innings_id,
            Delivery.is_legal_delivery.is_(True),
        )
        .group_by(Delivery.bowler_id, Delivery.over_number)
        .having(and_(legal_in_over == LEGAL_BALLS_PER_OVER, over_runs == 0))
        .subquery("maiden_overs")
    )


def head_to_head_stmt(team_a_id: int, team_b_id: int):
    from app.models.match import Match
    from app.models.enums import MatchStatus

    pair_match = and_(
        Match.status == MatchStatus.COMPLETED,
        Match.team_a_id.in_([team_a_id, team_b_id]),
        Match.team_b_id.in_([team_a_id, team_b_id]),
        Match.team_a_id != Match.team_b_id,
    )

    team_a_wins = func.sum(
        case((Match.winner_id == team_a_id, 1), else_=0)
    )
    team_b_wins = func.sum(
        case((Match.winner_id == team_b_id, 1), else_=0)
    )
    no_result = func.sum(
        case(
            (
                Match.winner_id.is_(None),
                1,
            ),
            else_=0,
        )
    )

    return select(
        func.count(Match.id).label("total_matches"),
        team_a_wins.label("team_a_wins"),
        team_b_wins.label("team_b_wins"),
        no_result.label("draws_or_no_result"),
    ).where(pair_match)
