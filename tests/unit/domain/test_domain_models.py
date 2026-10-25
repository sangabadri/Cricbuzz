import pytest
from app.schemas.enums import ExtraType, WicketType, InningsStatus
from app.domain.exceptions import (
    CreaseViolationError,
    OverProgressionError,
    BowlerRuleError,
    MatchStateError,
    HistoricalEditLockedError,
)
from app.domain.formats import T20FormatRules, ODIFormatRules, CustomFormatRules, get_format_rules
from app.domain.crease import Crease
from app.domain.over import BallEvent, Over
from app.domain.innings import InningsAggregate


def test_format_rules_strategy():
    t20 = get_format_rules("t20")
    assert isinstance(t20, T20FormatRules)
    assert t20.max_overs == 20
    assert t20.max_bowler_overs == 4

    odi = get_format_rules("odi")
    assert isinstance(odi, ODIFormatRules)
    assert odi.max_overs == 50
    assert odi.max_bowler_overs == 10

    custom = CustomFormatRules(max_overs=8, max_bowler_overs=2)
    assert custom.max_overs == 8
    assert custom.max_bowler_overs == 2


def test_crease_continuity_and_non_rebatting():
    crease = Crease()

    # Valid first pair
    crease.validate_continuity(10, 20)
    crease.striker_id = 10
    crease.non_striker_id = 20

    # Same player as striker and non-striker rejected
    with pytest.raises(CreaseViolationError) as exc:
        crease.validate_continuity(10, 10)
    assert "cannot be the same" in str(exc.value)

    # Unauthorized change of batter without a wicket rejected
    with pytest.raises(CreaseViolationError) as exc:
        crease.validate_continuity(10, 30)
    assert "must remain" in str(exc.value)

    # Wicket falls: striker 10 is dismissed
    crease.on_wicket(10)
    assert 10 in crease.dismissed_player_ids
    assert crease.striker_id is None
    assert crease.non_striker_id == 20

    # New batter 30 joins surviving batter 20
    crease.set_incoming_batter(30, on_strike=True)
    assert crease.striker_id == 30
    assert crease.non_striker_id == 20

    # Dismissed batter 10 attempts to bat again -> rejected!
    with pytest.raises(CreaseViolationError) as exc:
        crease.validate_continuity(10, 20)
    assert "already been dismissed" in str(exc.value)


def test_over_invariants_and_maiden():
    over = Over(over_number=0, bowler_id=1)

    # 4 dots, 1 wide, 2 dots
    over.add_ball(BallEvent(over=0, ball=1, bowler_id=1, batsman_id=10, non_striker_id=20, runs=0))
    over.add_ball(BallEvent(over=0, ball=2, bowler_id=1, batsman_id=10, non_striker_id=20, runs=0))
    over.add_ball(BallEvent(over=0, ball=3, bowler_id=1, batsman_id=10, non_striker_id=20, runs=0))
    over.add_ball(BallEvent(over=0, ball=4, bowler_id=1, batsman_id=10, non_striker_id=20, runs=0))
    # Wide
    over.add_ball(BallEvent(over=0, ball=5, bowler_id=1, batsman_id=10, non_striker_id=20, runs=0, extra_type=ExtraType.WIDE, extras=1))
    # 5th and 6th legal balls
    over.add_ball(BallEvent(over=0, ball=6, bowler_id=1, batsman_id=10, non_striker_id=20, runs=0))
    over.add_ball(BallEvent(over=0, ball=7, bowler_id=1, batsman_id=10, non_striker_id=20, runs=0))

    assert over.legal_balls_count == 6
    assert over.is_completed is True
    # 1 run conceded (the wide)
    assert over.runs_conceded == 1
    # Not a maiden because runs_conceded == 1
    assert over.is_maiden is False

    # Bowler mismatch rejected
    with pytest.raises(OverProgressionError):
        over.add_ball(BallEvent(over=0, ball=8, bowler_id=2, batsman_id=10, non_striker_id=20, runs=0))


def test_innings_aggregate_progression_and_quota():
    format_rules = T20FormatRules()
    innings = InningsAggregate(
        innings_number=1,
        batting_team_id=1,
        bowling_team_id=2,
        format_rules=format_rules,
    )

    # First ball must start at over 0, ball 1
    with pytest.raises(OverProgressionError):
        innings.validate_progression(over_number=1, ball_number=1)

    # Bowl over 0 by bowler 5
    for b in range(1, 7):
        innings.record_ball(
            BallEvent(over=0, ball=b, bowler_id=5, batsman_id=10, non_striker_id=20, runs=1)
        )

    assert innings.completed_overs == 1
    assert innings.total_runs == 6
    assert innings.status == InningsStatus.IN_PROGRESS

    # Bowler 5 cannot bowl consecutive over (Over 1)
    with pytest.raises(BowlerRuleError) as exc:
        innings.validate_bowler(over_number=1, bowler_id=5)
    assert "consecutive overs" in str(exc.value)

    # Bowl over 1 by bowler 6
    for b in range(1, 7):
        innings.record_ball(
            BallEvent(over=1, ball=b, bowler_id=6, batsman_id=10, non_striker_id=20, runs=0)
        )
    assert innings.completed_overs == 2


def test_innings_target_chased_and_undo():
    format_rules = T20FormatRules()
    # 2nd innings with target = 10
    innings = InningsAggregate(
        innings_number=2,
        batting_team_id=2,
        bowling_team_id=1,
        format_rules=format_rules,
        target=10,
    )

    # Bowl 2 deliveries
    innings.record_ball(BallEvent(over=0, ball=1, bowler_id=5, batsman_id=10, non_striker_id=20, runs=4))
    innings.record_ball(BallEvent(over=0, ball=2, bowler_id=5, batsman_id=10, non_striker_id=20, runs=6))

    assert innings.total_runs == 10
    assert innings.is_target_reached is True
    assert innings.is_completed is True
    assert innings.status == InningsStatus.COMPLETED

    # Cannot bowl in completed innings
    with pytest.raises(MatchStateError):
        innings.record_ball(BallEvent(over=0, ball=3, bowler_id=5, batsman_id=10, non_striker_id=20, runs=1))

    # UNDO the last ball (the 6)
    undone = innings.undo_last_ball()
    assert undone.runs == 6
    assert innings.total_runs == 4
    assert innings.is_target_reached is False
    assert innings.status == InningsStatus.IN_PROGRESS

    # UNDO first ball (the 4)
    undone2 = innings.undo_last_ball()
    assert undone2.runs == 4
    assert innings.total_runs == 0
    assert innings.status == InningsStatus.NOT_STARTED

    # Undo when empty raises HistoricalEditLockedError
    with pytest.raises(HistoricalEditLockedError):
        innings.undo_last_ball()
