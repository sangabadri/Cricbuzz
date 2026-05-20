from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.enums import MatchFormat, MatchStatus
from app.schemas.common import ORMModel


class CreateMatchRequest(BaseModel):
    team_a_name: str = Field(min_length=1, max_length=120)
    team_b_name: str = Field(min_length=1, max_length=120)
    venue: str = Field(min_length=1, max_length=200)
    match_date: date
    format: MatchFormat
    toss_winner_team: str | None = Field(
        default=None,
        description="Must be team_a_name or team_b_name when provided.",
    )
    elected_to_bat_first: bool | None = None
    start_first_innings: bool = False

    @model_validator(mode="after")
    def validate_toss(self) -> "CreateMatchRequest":
        if self.toss_winner_team and self.toss_winner_team not in (
            self.team_a_name,
            self.team_b_name,
        ):
            raise ValueError("toss_winner_team must match team_a_name or team_b_name")
        if self.start_first_innings and not self.toss_winner_team:
            raise ValueError("start_first_innings requires toss_winner_team")
        return self


class TeamBrief(ORMModel):
    id: int
    name: str


class InningsBrief(ORMModel):
    id: int
    innings_number: int
    batting_team_id: int
    bowling_team_id: int
    status: str
    max_overs: int | None
    max_bowler_overs: int | None


class MatchResponse(ORMModel):
    id: int
    venue: str
    match_date: date
    format: MatchFormat
    status: MatchStatus
    team_a: TeamBrief
    team_b: TeamBrief
    toss_winner_id: int | None
    elected_to_bat_first: bool | None
    first_innings: InningsBrief | None = None
