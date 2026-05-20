from pydantic import BaseModel, Field

from app.models.enums import BattingStyle, BowlingStyle, PlayerRole
from app.schemas.common import ORMModel


class PlayerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: PlayerRole
    batting_style: BattingStyle | None = None
    bowling_style: BowlingStyle | None = None


class RosterPlayerCreate(BaseModel):
    """Add an existing or new player to a match squad."""

    player_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: PlayerRole | None = None
    batting_style: BattingStyle | None = None
    bowling_style: BowlingStyle | None = None
    squad_role: PlayerRole
    is_playing_xi: bool = True
    is_captain: bool = False
    is_wicketkeeper: bool = False


class AddPlayersRequest(BaseModel):
    team_id: int
    players: list[RosterPlayerCreate] = Field(min_length=1)


class PlayerResponse(ORMModel):
    id: int
    name: str
    role: PlayerRole
    batting_style: BattingStyle | None
    bowling_style: BowlingStyle | None


class RosterEntryResponse(ORMModel):
    id: int
    match_id: int
    team_id: int
    player_id: int
    squad_role: PlayerRole
    is_playing_xi: bool
    is_captain: bool
    is_wicketkeeper: bool
    player: PlayerResponse


class AddPlayersResponse(BaseModel):
    roster_entries: list[RosterEntryResponse]
