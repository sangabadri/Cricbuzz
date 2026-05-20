from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PlayerRole

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.player import Player
    from app.models.team import Team


class MatchRoster(Base):
    """
    Squad and playing XI for a team in a specific match.
    `squad_role` may differ from the player's default profile role.
    """

    __tablename__ = "match_rosters"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "team_id",
            "player_id",
            name="uq_roster_match_team_player",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    squad_role: Mapped[PlayerRole] = mapped_column(
        Enum(PlayerRole, name="player_role", native_enum=False),
        nullable=False,
    )
    is_playing_xi: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    is_captain: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_wicketkeeper: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    match: Mapped[Match] = relationship(back_populates="roster")
    team: Mapped[Team] = relationship(back_populates="roster_entries")
    player: Mapped[Player] = relationship(back_populates="roster_entries")
