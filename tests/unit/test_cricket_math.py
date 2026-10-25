import pytest
from app.schemas.enums import MatchFormat

def balls_to_overs_str(balls: int) -> str:
    return f"{balls // 6}.{balls % 6}"

def balls_to_overs_decimal(balls: int) -> float:
    return balls / 6.0

def calc_run_rate(runs: int, balls: int) -> float:
    if balls == 0:
        return 0.0
    return round(runs / (balls / 6.0), 2)

def calc_strike_rate(runs: int, balls: int) -> float:
    if balls == 0:
        return 0.0
    return round((runs / balls) * 100.0, 2)

def calc_economy(runs_conceded: int, balls_bowled: int) -> float:
    if balls_bowled == 0:
        return 0.0
    return round(runs_conceded / (balls_bowled / 6.0), 2)

def test_balls_to_overs_str_formatting():
    assert balls_to_overs_str(0) == "0.0"
    assert balls_to_overs_str(1) == "0.1"
    assert balls_to_overs_str(5) == "0.5"
    assert balls_to_overs_str(6) == "1.0"
    assert balls_to_overs_str(7) == "1.1"
    assert balls_to_overs_str(11) == "1.5"
    assert balls_to_overs_str(12) == "2.0"
    assert balls_to_overs_str(119) == "19.5"
    assert balls_to_overs_str(120) == "20.0"

def test_match_format_rules():
    assert MatchFormat.T20.max_overs == 20
    assert MatchFormat.T20.max_bowler_overs == 4
    assert MatchFormat.T20.total_innings == 2

    assert MatchFormat.ODI.max_overs == 50
    assert MatchFormat.ODI.max_bowler_overs == 10
    assert MatchFormat.ODI.total_innings == 2

def test_run_rate_calculation():
    # Zero balls bowled should never divide by zero
    assert calc_run_rate(0, 0) == 0.0
    assert calc_run_rate(10, 0) == 0.0

    # 45 runs in 4.3 overs (27 balls) -> 45 / 4.5 = 10.0
    assert calc_run_rate(45, 27) == 10.0

    # 180 runs in 20.0 overs (120 balls) -> 9.0
    assert calc_run_rate(180, 120) == 9.0

    # 10 runs in 1 over (6 balls) -> 10.0
    assert calc_run_rate(10, 6) == 10.0

def test_strike_rate_calculation():
    assert calc_strike_rate(0, 0) == 0.0
    assert calc_strike_rate(50, 25) == 200.0
    assert calc_strike_rate(35, 28) == 125.0
    assert calc_strike_rate(0, 10) == 0.0
    # 47 runs off 32 balls -> 146.88
    assert calc_strike_rate(47, 32) == 146.88

def test_economy_calculation():
    assert calc_economy(0, 0) == 0.0
    # 24 runs in 4.0 overs (24 balls) -> 6.0
    assert calc_economy(24, 24) == 6.0
    # 35 runs in 3.4 overs (22 balls) -> 35 / (22/6) = 9.55
    assert calc_economy(35, 22) == 9.55
    # Maiden over (0 runs in 6 balls) -> 0.0
    assert calc_economy(0, 6) == 0.0
