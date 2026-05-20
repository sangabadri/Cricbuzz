from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BattingStyle, BowlingStyle, PlayerRole

if TYPE_CHECKING:
    from app.models.delivery import Delivery
    from app.models.match import Match
    from app.models.match_roster import MatchRoster


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[PlayerRole] = mapped_column(
        Enum(PlayerRole, name="player_role", native_enum=False),
        nullable=False,
    )
    batting_style: Mapped[BattingStyle | None] = mapped_column(
        Enum(BattingStyle, name="batting_style", native_enum=False),
    )
    bowling_style: Mapped[BowlingStyle | None] = mapped_column(
        Enum(BowlingStyle, name="bowling_style", native_enum=False),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    roster_entries: Mapped[list[MatchRoster]] = relationship(
        back_populates="player",
    )
    striker_deliveries: Mapped[list[Delivery]] = relationship(
        back_populates="striker",
        foreign_keys="Delivery.striker_id",
    )
    bowler_deliveries: Mapped[list[Delivery]] = relationship(
        back_populates="bowler",
        foreign_keys="Delivery.bowler_id",
    )
    dismissals: Mapped[list[Delivery]] = relationship(
        back_populates="dismissed_player",
        foreign_keys="Delivery.dismissed_player_id",
    )
    fielding_dismissals: Mapped[list[Delivery]] = relationship(
        back_populates="fielder",
        foreign_keys="Delivery.fielder_id",
    )
    player_of_match_awards: Mapped[list[Match]] = relationship(
        back_populates="player_of_match",
        foreign_keys="Match.player_of_match_id",
    )
