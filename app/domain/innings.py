from app.schemas.enums import InningsStatus
from app.domain.exceptions import (
    OverProgressionError,
    BowlerRuleError,
    MatchStateError,
    HistoricalEditLockedError,
)
from app.domain.formats import FormatRules
from app.domain.crease import Crease
from app.domain.over import BallEvent, Over


class InningsAggregate:
    """
    Aggregate root governing the complete cricket lifecycle and state invariants of an innings.
    100% pure in-memory domain model with zero database or web framework dependencies.
    """

    def __init__(
        self,
        innings_number: int,
        batting_team_id: int,
        bowling_team_id: int,
        format_rules: FormatRules,
        target: int | None = None,
        status: InningsStatus = InningsStatus.NOT_STARTED,
        balls: list[BallEvent] | None = None,
    ):
        self.innings_number = innings_number
        self.batting_team_id = batting_team_id
        self.bowling_team_id = bowling_team_id
        self.format_rules = format_rules
        self.target = target
        self.status = status
        self.balls: list[BallEvent] = []
        self.overs: list[Over] = []
        self.crease = Crease()

        # Replay existing balls into aggregate state if hydrating
        for b in (balls or []):
            self._apply_ball_internal(b)

    @property
    def total_runs(self) -> int:
        return sum(b.total_runs for b in self.balls)

    @property
    def total_wickets(self) -> int:
        return sum(1 for b in self.balls if b.wicket_type is not None)

    @property
    def total_legal_balls(self) -> int:
        return sum(1 for b in self.balls if b.is_legal)

    @property
    def completed_overs(self) -> int:
        return self.total_legal_balls // 6

    @property
    def balls_in_current_over(self) -> int:
        return self.total_legal_balls % 6

    @property
    def is_all_out(self) -> bool:
        return self.total_wickets >= 10

    @property
    def is_target_reached(self) -> bool:
        return self.target is not None and self.total_runs >= self.target

    @property
    def is_max_overs_reached(self) -> bool:
        if not self.overs:
            return False
        last_over = self.overs[-1]
        return (last_over.over_number == self.format_rules.max_overs - 1) and last_over.is_completed

    @property
    def is_completed(self) -> bool:
        return self.is_target_reached or self.is_all_out or self.is_max_overs_reached

    def validate_progression(self, over_number: int, ball_number: int):
        if over_number >= self.format_rules.max_overs:
            raise OverProgressionError(f"Over {over_number} exceeds maximum overs ({self.format_rules.max_overs})")

        if not self.overs:
            if over_number != 0:
                raise OverProgressionError(f"First over of the innings must be over 0, got {over_number}")
        else:
            last_over = self.overs[-1]
            if not last_over.is_completed:
                if over_number != last_over.over_number:
                    raise OverProgressionError(
                        f"Over {last_over.over_number} is still in progress (only {last_over.legal_balls_count} legal balls bowled). Cannot start over {over_number}"
                    )
            else:
                if over_number != last_over.over_number + 1:
                    raise OverProgressionError(
                        f"Over {last_over.over_number} is completed. Expected next over to be {last_over.over_number + 1}, got {over_number}"
                    )

        # Ball numbering validation within the current over
        balls_in_this_over = [b for b in self.balls if b.over == over_number]
        expected_ball = len(balls_in_this_over) + 1
        if ball_number != expected_ball:
            raise OverProgressionError(f"Invalid ball number {ball_number}. Expected ball {expected_ball}")

    def validate_bowler(self, over_number: int, bowler_id: int):
        # 1. Bowler cannot change mid-over
        balls_in_this_over = [b for b in self.balls if b.over == over_number]
        if balls_in_this_over and balls_in_this_over[0].bowler_id != bowler_id:
            raise BowlerRuleError(f"Over {over_number} is already being bowled by player {balls_in_this_over[0].bowler_id}")

        # 2. Bowler cannot bowl consecutive overs
        if over_number > 0:
            balls_in_prev_over = [b for b in self.balls if b.over == over_number - 1]
            if balls_in_prev_over and balls_in_prev_over[0].bowler_id == bowler_id:
                raise BowlerRuleError(f"Bowler {bowler_id} cannot bowl consecutive overs")

        # 3. Bowler overs quota
        completed_bowler_overs = len(
            set(b.over for b in self.balls if b.bowler_id == bowler_id and b.over < over_number)
        )
        if completed_bowler_overs >= self.format_rules.max_bowler_overs:
            raise BowlerRuleError(
                f"Bowler {bowler_id} has completed maximum {self.format_rules.max_bowler_overs} overs quota"
            )

    def _apply_ball_internal(self, ball: BallEvent):
        """Applies a delivery event to internal overs, crease, and deliveries collection."""
        self.balls.append(ball)

        # Append to existing over or create new over
        if not self.overs or self.overs[-1].over_number != ball.over:
            new_over = Over(over_number=ball.over, bowler_id=ball.bowler_id)
            new_over.add_ball(ball)
            self.overs.append(new_over)
        else:
            self.overs[-1].add_ball(ball)

        # Update crease state
        self.crease.striker_id = ball.batsman_id
        self.crease.non_striker_id = ball.non_striker_id
        if ball.wicket_type is not None and ball.player_out_id is not None:
            self.crease.on_wicket(ball.player_out_id)

    def record_ball(self, ball: BallEvent) -> BallEvent:
        """Validates all cricket rules and records the delivery in the aggregate."""
        if self.status == InningsStatus.COMPLETED:
            raise MatchStateError(f"Innings {self.innings_number} is already completed")

        # Invariant validations
        self.validate_progression(ball.over, ball.ball)
        self.validate_bowler(ball.over, ball.bowler_id)
        self.crease.validate_continuity(ball.batsman_id, ball.non_striker_id)

        # Apply delivery
        self._apply_ball_internal(ball)

        # Transition status
        if self.status == InningsStatus.NOT_STARTED:
            self.status = InningsStatus.IN_PROGRESS

        if self.is_completed:
            self.status = InningsStatus.COMPLETED

        return ball

    def undo_last_ball(self) -> BallEvent:
        """Removes the last delivery and rolls back aggregate state."""
        if not self.balls:
            raise HistoricalEditLockedError("No deliveries found in this innings to undo")

        removed_ball = self.balls.pop()

        # Re-initialize overs and crease from remaining deliveries
        remaining = list(self.balls)
        self.balls = []
        self.overs = []
        self.crease = Crease()
        for b in remaining:
            self._apply_ball_internal(b)

        # Re-evaluate status
        if not self.balls:
            self.status = InningsStatus.NOT_STARTED
        elif self.is_completed:
            self.status = InningsStatus.COMPLETED
        else:
            self.status = InningsStatus.IN_PROGRESS

        return removed_ball
