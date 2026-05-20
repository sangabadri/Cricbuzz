from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.match_roster import MatchRoster


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(16), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    home_matches: Mapped[list[Match]] = relationship(
        back_populates="team_a",
        foreign_keys="Match.team_a_id",
    )
    away_matches: Mapped[list[Match]] = relationship(
        back_populates="team_b",
        foreign_keys="Match.team_b_id",
    )
    roster_entries: Mapped[list[MatchRoster]] = relationship(
        back_populates="team",
    )
