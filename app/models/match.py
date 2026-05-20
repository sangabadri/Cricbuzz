from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MatchFormat, MatchStatus, format_innings_over_cap

if TYPE_CHECKING:
    from app.models.innings import Innings
    from app.models.match_roster import MatchRoster
    from app.models.player import Player
    from app.models.team import Team


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_a_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    team_b_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    venue: Mapped[str] = mapped_column(String(200), nullable=False)
    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    format: Mapped[MatchFormat] = mapped_column(
        Enum(MatchFormat, name="match_format", native_enum=False),
        nullable=False,
    )
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status", native_enum=False),
        nullable=False,
        default=MatchStatus.SCHEDULED,
        server_default=MatchStatus.SCHEDULED.value,
    )
    toss_winner_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    elected_to_bat_first: Mapped[bool | None] = mapped_column()
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    result_summary: Mapped[str | None] = mapped_column(Text)
    player_of_match_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    team_a: Mapped[Team] = relationship(
        foreign_keys=[team_a_id],
        back_populates="home_matches",
    )
    team_b: Mapped[Team] = relationship(
        foreign_keys=[team_b_id],
        back_populates="away_matches",
    )
    toss_winner: Mapped[Team | None] = relationship(foreign_keys=[toss_winner_id])
    winner: Mapped[Team | None] = relationship(foreign_keys=[winner_id])
    player_of_match: Mapped[Player | None] = relationship(
        back_populates="player_of_match_awards",
    )
    roster: Mapped[list[MatchRoster]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
    )
    innings: Mapped[list[Innings]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="Innings.innings_number",
    )

    @property
    def max_overs_per_innings(self) -> int | None:
        return format_innings_over_cap(self.format)
