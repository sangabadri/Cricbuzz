from dataclasses import dataclass
from app.schemas.enums import ExtraType, WicketType
from app.domain.exceptions import OverProgressionError


@dataclass
class BallEvent:
    """Represents a single delivery event in the pure domain layer."""
    over: int
    ball: int
    bowler_id: int
    batsman_id: int
    non_striker_id: int
    runs: int
    extra_type: ExtraType | None = None
    extras: int = 0
    wicket_type: WicketType | None = None
    player_out_id: int | None = None
    fielder_id: int | None = None
    commentary: str | None = None

    @property
    def is_legal(self) -> bool:
        """Wides and no-balls are not legal balls in cricket."""
        return self.extra_type not in (ExtraType.WIDE, ExtraType.NOBALL)

    @property
    def total_runs(self) -> int:
        return self.runs + self.extras

    @property
    def runs_conceded_by_bowler(self) -> int:
        """Byes and leg-byes are not charged to the bowler."""
        if self.extra_type in (ExtraType.BYE, ExtraType.LEGBYE):
            return 0
        return self.runs + self.extras

    @property
    def is_bowler_wicket(self) -> bool:
        """Run-outs are not credited to the bowler's wicket tally."""
        return self.wicket_type in (
            WicketType.BOWLED,
            WicketType.CAUGHT,
            WicketType.LBW,
            WicketType.STUMPED,
            WicketType.HIT_WICKET,
            WicketType.CAUGHT_AND_BOWLED,
        )


class Over:
    """Encapsulates deliveries within an over and computes over-level invariants."""

    def __init__(self, over_number: int, bowler_id: int, balls: list[BallEvent] | None = None):
        self.over_number = over_number
        self.bowler_id = bowler_id
        self.balls: list[BallEvent] = list(balls or [])

    @property
    def legal_balls_count(self) -> int:
        return sum(1 for b in self.balls if b.is_legal)

    @property
    def is_completed(self) -> bool:
        return self.legal_balls_count == 6

    @property
    def runs_conceded(self) -> int:
        return sum(b.runs_conceded_by_bowler for b in self.balls)

    @property
    def wickets_taken(self) -> int:
        return sum(1 for b in self.balls if b.is_bowler_wicket)

    @property
    def is_maiden(self) -> bool:
        return self.is_completed and self.runs_conceded == 0

    def add_ball(self, ball: BallEvent):
        if ball.over != self.over_number:
            raise OverProgressionError(f"Ball over {ball.over} does not match Over {self.over_number}")
        if ball.bowler_id != self.bowler_id:
            raise OverProgressionError(
                f"Over {self.over_number} is already being bowled by player {self.bowler_id}"
            )
        self.balls.append(ball)
