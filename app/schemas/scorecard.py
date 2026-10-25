from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.enums import MatchFormat, MatchStatus, InningsStatus, TossDecision, ExtraType, WicketType


class OversRecord(BaseModel):
    """Encapsulates over and ball progression as numeric fields."""
    completed_overs: int
    balls: int
    total_legal_balls: int


class BestBowling(BaseModel):
    """Structured bowling best figures."""
    wickets: int
    runs: int


class HighestScore(BaseModel):
    """Structured highest batting score."""
    runs: int
    is_not_out: bool


class DismissalInfo(BaseModel):
    """Structured dismissal information."""
    wicket_type: WicketType
    bowler_id: int
    bowler_name: str
    fielder_id: int | None = None
    fielder_name: str | None = None


class ExtrasBreakdown(BaseModel):
    byes: int
    leg_byes: int
    wides: int
    no_balls: int
    total: int


class PlayerSummary(BaseModel):
    id: int
    name: str


class BatterScorecard(BaseModel):
    player_id: int
    player_name: str
    runs: int
    balls: int
    fours: int
    sixes: int
    strike_rate: float | None = None
    is_out: bool
    dismissal: DismissalInfo | None = None


# Backwards compatibility alias for BatterScorecard
BatsmanStats = BatterScorecard


class BowlerScorecard(BaseModel):
    player_id: int
    player_name: str
    overs: OversRecord
    maidens: int
    runs: int
    wickets: int
    economy: float | None = None
    wides: int
    no_balls: int


# Backwards compatibility alias for BowlerScorecard
BowlerStats = BowlerScorecard


class FallOfWicket(BaseModel):
    wicket_number: int
    player_id: int
    player_name: str
    score: int
    overs: OversRecord


class PartnershipBatter(BaseModel):
    player_id: int
    player_name: str
    runs: int
    balls: int


class Partnership(BaseModel):
    wicket_number: int
    runs: int
    balls: int
    overs: OversRecord
    batters: list[PartnershipBatter]


class InningsScorecard(BaseModel):
    innings_number: int
    batting_team_id: int
    batting_team_name: str
    bowling_team_id: int
    bowling_team_name: str
    runs: int
    wickets: int
    overs: OversRecord
    current_run_rate: float
    target: int | None = None
    required_run_rate: float | None = None
    status: InningsStatus
    batting: list[BatterScorecard]
    bowling: list[BowlerScorecard]
    fall_of_wickets: list[FallOfWicket]
    partnerships: list[Partnership]
    extras: ExtrasBreakdown


class MatchScorecardResponse(BaseModel):
    match_id: int
    format: MatchFormat
    status: MatchStatus
    venue: str
    match_date: datetime
    team_a_id: int
    team_a_name: str
    team_b_id: int
    team_b_name: str
    toss_winner_id: int | None = None
    toss_winner_name: str | None = None
    toss_decision: TossDecision | None = None
    winner_id: int | None = None
    winner_name: str | None = None
    mom_id: int | None = None
    mom_name: str | None = None
    innings: list[InningsScorecard]


class LiveCurrentOverBall(BaseModel):
    ball_number: int
    runs: int
    extra_type: ExtraType | None = None
    extras: int = 0
    is_wicket: bool = False
    wicket_type: WicketType | None = None


class LiveBatter(BaseModel):
    player_id: int
    name: str
    runs: int
    balls: int
    fours: int
    sixes: int
    strike_rate: float | None = None


class LiveBowler(BaseModel):
    player_id: int
    name: str
    overs: OversRecord
    maidens: int
    runs: int
    wickets: int
    economy: float | None = None


class LiveMatchResponse(BaseModel):
    match_id: int
    status: MatchStatus
    format: MatchFormat
    venue: str
    team_a_name: str
    team_b_name: str
    current_innings_number: int | None = None
    batting_team_name: str | None = None
    bowling_team_name: str | None = None
    runs: int = 0
    wickets: int = 0
    overs: OversRecord = Field(default_factory=lambda: OversRecord(completed_overs=0, balls=0, total_legal_balls=0))
    current_run_rate: float = 0.0
    target: int | None = None
    runs_needed: int | None = None
    balls_remaining: int | None = None
    required_run_rate: float | None = None
    striker: LiveBatter | None = None
    non_striker: LiveBatter | None = None
    current_bowler: LiveBowler | None = None
    current_over_balls: list[LiveCurrentOverBall] = Field(default_factory=list)
    last_event_runs: int | None = None
    last_event_is_wicket: bool = False
