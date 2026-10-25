from app.domain.exceptions import CreaseViolationError


class Crease:
    """
    Encapsulates the batting pair currently at the crease and enforces crease continuity
    and non-rebatting invariants across an innings.
    """

    def __init__(
        self,
        striker_id: int | None = None,
        non_striker_id: int | None = None,
        dismissed_player_ids: set[int] | None = None,
    ):
        self.striker_id = striker_id
        self.non_striker_id = non_striker_id
        self.dismissed_player_ids: set[int] = set(dismissed_player_ids or [])

    @property
    def current_pair(self) -> set[int]:
        """Returns the set of player IDs currently active at the crease."""
        return {p for p in (self.striker_id, self.non_striker_id) if p is not None}

    def validate_continuity(self, incoming_striker: int, incoming_non_striker: int):
        """
        Validates that:
        1. Striker and non-striker are distinct players.
        2. Neither player has been previously dismissed in this innings.
        3. The active pair matches the surviving pair from the previous delivery.
        """
        if incoming_striker == incoming_non_striker:
            raise CreaseViolationError("Striker and non-striker cannot be the same player")

        if incoming_striker in self.dismissed_player_ids:
            raise CreaseViolationError(
                f"Batsman {incoming_striker} has already been dismissed in this innings and cannot bat again"
            )
        if incoming_non_striker in self.dismissed_player_ids:
            raise CreaseViolationError(
                f"Non-striker {incoming_non_striker} has already been dismissed in this innings and cannot bat again"
            )

        # If both batters are established at the crease, both must remain
        if len(self.current_pair) == 2:
            incoming_pair = {incoming_striker, incoming_non_striker}
            if incoming_pair != self.current_pair:
                raise CreaseViolationError(
                    f"Batters at crease must remain {self.current_pair} since no wicket fell on previous ball"
                )
        elif len(self.current_pair) == 1:
            surviving_batter = next(iter(self.current_pair))
            if surviving_batter not in (incoming_striker, incoming_non_striker):
                raise CreaseViolationError(
                    f"Surviving batter {surviving_batter} must remain at the crease on the next ball"
                )

    def on_wicket(self, player_out_id: int):
        """Records a dismissal at the crease and frees up that batter's crease slot."""
        if player_out_id not in self.current_pair:
            raise CreaseViolationError(f"Player {player_out_id} is not currently at the crease to be dismissed")
        self.dismissed_player_ids.add(player_out_id)
        if self.striker_id == player_out_id:
            self.striker_id = None
        else:
            self.non_striker_id = None

    def set_incoming_batter(self, new_batter_id: int, on_strike: bool = True):
        """Positions a new incoming batter at the vacant crease slot."""
        if new_batter_id in self.dismissed_player_ids:
            raise CreaseViolationError(f"Player {new_batter_id} has already been dismissed in this innings")
        if on_strike:
            self.striker_id = new_batter_id
        else:
            self.non_striker_id = new_batter_id

    def rotate_strike(self):
        """Rotates striker and non-striker ends."""
        self.striker_id, self.non_striker_id = self.non_striker_id, self.striker_id
