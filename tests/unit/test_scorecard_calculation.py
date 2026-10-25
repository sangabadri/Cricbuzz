from types import SimpleNamespace
from app.models.delivery import Delivery
from app.models.innings import Innings
from app.schemas.enums import ExtraType, WicketType, InningsStatus
from app.services.scorecard import _build_partnership, build_innings_scorecard


def make_delivery(
    over: int,
    ball: int,
    bowler_id: int,
    batsman_id: int,
    non_striker_id: int,
    runs: int = 0,
    extra_type: ExtraType | None = None,
    extras: int = 0,
    wicket_type: WicketType | None = None,
    player_out_id: int | None = None,
    fielder_id: int | None = None,
) -> Delivery:
    d = Delivery()
    d.id = over * 10 + ball
    d.innings_id = 1
    d.over = over
    d.ball = ball
    d.bowler_id = bowler_id
    d.batsman_id = batsman_id
    d.non_striker_id = non_striker_id
    d.runs = runs
    d.extra_type = extra_type
    d.extras = extras
    d.wicket_type = wicket_type
    d.player_out_id = player_out_id
    d.fielder_id = fielder_id
    return d


def test_build_partnership_basic():
    # 2 deliveries: Batter 10 scores 4, Batter 10 scores 1
    d1 = make_delivery(0, 1, bowler_id=1, batsman_id=10, non_striker_id=20, runs=4)
    d2 = make_delivery(0, 2, bowler_id=1, batsman_id=10, non_striker_id=20, runs=1)
    # Batter 20 scores 2
    d3 = make_delivery(0, 3, bowler_id=1, batsman_id=20, non_striker_id=10, runs=2)
    # Wide ball (extra 1)
    d4 = make_delivery(0, 4, bowler_id=1, batsman_id=20, non_striker_id=10, extra_type=ExtraType.WIDE, extras=1)

    deliveries = [d1, d2, d3, d4]
    player_names = {10: "Batter Ten", 20: "Batter Twenty"}
    part = _build_partnership(wicket_number=1, deliveries=deliveries, player_names=player_names)

    assert part.wicket_number == 1
    # Total runs = 4 + 1 + 2 + 1(wide) = 8
    assert part.runs == 8
    # Legal balls = 3 (wide is not legal ball)
    assert part.balls == 3
    assert part.overs.completed_overs == 0
    assert part.overs.balls == 3
    assert part.overs.total_legal_balls == 3

    # Check batter breakdowns
    b10 = next(b for b in part.batters if b.player_id == 10)
    b20 = next(b for b in part.batters if b.player_id == 20)
    assert b10.runs == 5
    assert b10.balls == 2
    assert b20.runs == 2
    assert b20.balls == 1


def test_build_innings_scorecard_comprehensive():
    inn = Innings(
        id=1,
        match_id=1,
        innings_number=1,
        batting_team_id=100,
        bowling_team_id=200,
        status=InningsStatus.COMPLETED,
    )

    squad_rows = [
        SimpleNamespace(id=1, name="Batter A", team_id=100, is_playing_xi=True),
        SimpleNamespace(id=2, name="Batter B", team_id=100, is_playing_xi=True),
        SimpleNamespace(id=3, name="Batter C", team_id=100, is_playing_xi=True),
        SimpleNamespace(id=10, name="Bowler X", team_id=200, is_playing_xi=True),
        SimpleNamespace(id=20, name="Bowler Y", team_id=200, is_playing_xi=True),
    ]

    # Over 0 bowled by Bowler X:
    over0 = [
        make_delivery(0, 1, bowler_id=10, batsman_id=1, non_striker_id=2, runs=0),
        make_delivery(0, 2, bowler_id=10, batsman_id=1, non_striker_id=2, runs=4),
        make_delivery(0, 3, bowler_id=10, batsman_id=1, non_striker_id=2, runs=1),
        make_delivery(0, 4, bowler_id=10, batsman_id=2, non_striker_id=1, runs=6),
        make_delivery(0, 5, bowler_id=10, batsman_id=2, non_striker_id=1, runs=1),
        make_delivery(0, 6, bowler_id=10, batsman_id=1, non_striker_id=2, runs=0),
    ]

    # Over 1 bowled by Bowler Y (Maiden over with a wicket)
    over1 = [
        make_delivery(1, 1, bowler_id=20, batsman_id=2, non_striker_id=1, runs=0, wicket_type=WicketType.BOWLED, player_out_id=2),
        make_delivery(1, 2, bowler_id=20, batsman_id=3, non_striker_id=1, runs=0),
        make_delivery(1, 3, bowler_id=20, batsman_id=3, non_striker_id=1, runs=0),
        make_delivery(1, 4, bowler_id=20, batsman_id=3, non_striker_id=1, runs=0),
        make_delivery(1, 5, bowler_id=20, batsman_id=3, non_striker_id=1, runs=0),
        make_delivery(1, 6, bowler_id=20, batsman_id=3, non_striker_id=1, runs=0),
    ]

    all_delivs = over0 + over1
    scorecard = build_innings_scorecard(
        innings=inn,
        deliveries=all_delivs,
        squad_rows=squad_rows,
        max_overs=20,
    )

    # Total runs: 12 runs, 1 wicket, 2.0 overs
    assert scorecard.runs == 12
    assert scorecard.wickets == 1
    assert scorecard.overs.completed_overs == 2
    assert scorecard.overs.balls == 0
    assert scorecard.overs.total_legal_balls == 12

    # Batsman stats
    b1 = next(b for b in scorecard.batting if b.player_id == 1)
    b2 = next(b for b in scorecard.batting if b.player_id == 2)
    b3 = next(b for b in scorecard.batting if b.player_id == 3)

    assert b1.runs == 5
    assert b1.balls == 4
    assert b1.fours == 1
    assert b1.sixes == 0
    assert not b1.is_out

    assert b2.runs == 7
    assert b2.balls == 3
    assert b2.fours == 0
    assert b2.sixes == 1
    assert b2.is_out
    assert b2.dismissal is not None
    assert b2.dismissal.wicket_type == WicketType.BOWLED
    assert b2.dismissal.bowler_name == "Bowler Y"

    assert b3.runs == 0
    assert b3.balls == 5
    assert not b3.is_out

    # Bowler stats
    bowler_x = next(b for b in scorecard.bowling if b.player_id == 10)
    bowler_y = next(b for b in scorecard.bowling if b.player_id == 20)

    assert bowler_x.overs.completed_overs == 1
    assert bowler_x.overs.balls == 0
    assert bowler_x.overs.total_legal_balls == 6
    assert bowler_x.runs == 12
    assert bowler_x.wickets == 0
    assert bowler_x.maidens == 0

    assert bowler_y.overs.completed_overs == 1
    assert bowler_y.overs.balls == 0
    assert bowler_y.overs.total_legal_balls == 6
    assert bowler_y.runs == 0
    assert bowler_y.wickets == 1
    assert bowler_y.maidens == 1

    # Fall of Wickets
    assert len(scorecard.fall_of_wickets) == 1
    fow = scorecard.fall_of_wickets[0]
    assert fow.wicket_number == 1
    assert fow.score == 12
    assert fow.player_id == 2
    assert fow.player_name == "Batter B"
    assert fow.overs.completed_overs == 1
    assert fow.overs.balls == 1
    assert fow.overs.total_legal_balls == 7

    # Partnerships: 1st wicket partnership + unfinished 2nd wicket partnership
    assert len(scorecard.partnerships) == 2
    p1 = scorecard.partnerships[0]
    assert p1.wicket_number == 1
    assert p1.runs == 12

    p2 = scorecard.partnerships[1]
    assert p2.wicket_number == 2
    assert p2.runs == 0
