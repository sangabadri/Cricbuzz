from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import MatchFormat, MatchStatus, WicketType


class LiveScorecardResponse(BaseModel):
    match_id: int
    innings_id: int
    innings_number: int
    batting_team_id: int
    batting_team_name: str
    status: str
    total_runs: int
    total_wickets: int
    overs_display: str
    legal_balls_bowled: int
    extras_total: int
    current_run_rate: float | None
    required_run_rate: float | None
    runs_required: int | None
    balls_remaining: int | None
    target_runs: int | None
    last_five_overs_runs: int
    last_five_overs_run_rate: float | None


class BatsmanCardEntry(BaseModel):
    player_id: int
    player_name: str
    runs: int
    balls_faced: int
    strike_rate: float | None
    fours: int
    sixes: int
    dismissal: str


class BatsmanCardResponse(BaseModel):
    innings_id: int
    batsmen: list[BatsmanCardEntry]


class BowlerFiguresEntry(BaseModel):
    player_id: int
    player_name: str
    overs_display: str
    legal_balls_bowled: int
    maidens: int
    runs_conceded: int
    wickets: int
    economy_rate: float | None


class BowlerFiguresResponse(BaseModel):
    innings_id: int
    bowlers: list[BowlerFiguresEntry]


class PartnershipEntry(BaseModel):
    partnership_number: int
    batsman_1_id: int
    batsman_1_name: str
    batsman_2_id: int
    batsman_2_name: str
    runs: int
    balls_faced: int
    is_current: bool


class PartnershipTrackerResponse(BaseModel):
    innings_id: int
    current_partnership: PartnershipEntry | None
    past_partnerships: list[PartnershipEntry]


class FallOfWicketEntry(BaseModel):
    wicket_number: int
    runs_at_fall: int
    overs_at_fall: str
    dismissed_player_id: int
    dismissed_player_name: str
    dismissal: str
    sequence_number: int


class InningsSummaryBlock(BaseModel):
    innings_number: int
    batting_team_name: str
    total_runs: int
    total_wickets: int
    overs_display: str
    status: str


class MatchSummaryResponse(BaseModel):
    match_id: int
    venue: str
    match_date: date
    format: MatchFormat
    status: MatchStatus
    team_a_name: str
    team_b_name: str
    winner_name: str | None
    result_summary: str | None
    player_of_match_id: int | None
    player_of_match_name: str | None
    innings: list[InningsSummaryBlock]
    fall_of_wickets: list[FallOfWicketEntry]


class HeadToHeadResponse(BaseModel):
    team_a_id: int
    team_a_name: str
    team_b_id: int
    team_b_name: str
    team_a_wins: int
    team_b_wins: int
    draws_or_no_result: int
    total_matches: int
