from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    LEGAL_BALLS_PER_OVER,
    ExtraType,
    WicketType,
    is_legal_delivery_extra,
)

if TYPE_CHECKING:
    from app.models.innings import Innings
    from app.models.player import Player


class Delivery(Base):
    """
    Ball-by-ball event log.

    Identity within an over:
    - `delivery_in_over`: 1-based index of every physical delivery (legal + illegal).
      Unique per (innings, over) — prevents duplicate ball entries.
    - `legal_ball_in_over`: 1–6 for legal deliveries only; NULL for wide/no-ball.

  Scoring:
    - `runs_off_bat`: runs credited to the striker's bat.
    - `extra_type` / `extra_runs`: wides, no-balls, byes, leg-byes.
    - `total_runs` on the ball = runs_off_bat + extra_runs (application layer).

    Wides and no-balls set `is_legal_delivery=False` and must not increment
    innings.legal_balls_bowled.
    """

    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint(
            "innings_id",
            "over_number",
            "delivery_in_over",
            name="uq_delivery_innings_over_slot",
        ),
        UniqueConstraint(
            "innings_id",
            "over_number",
            "legal_ball_in_over",
            name="uq_delivery_innings_over_legal_ball",
        ),
        UniqueConstraint(
            "innings_id",
            "sequence_number",
            name="uq_delivery_innings_sequence",
        ),
        CheckConstraint("over_number >= 0", name="ck_delivery_over_nonneg"),
        CheckConstraint("delivery_in_over >= 1", name="ck_delivery_in_over_positive"),
        CheckConstraint(
            "(is_legal_delivery = true AND legal_ball_in_over BETWEEN 1 AND 6) OR "
            "(is_legal_delivery = false AND legal_ball_in_over IS NULL)",
            name="ck_delivery_legal_ball_slot",
        ),
        CheckConstraint("runs_off_bat >= 0", name="ck_delivery_runs_off_bat"),
        CheckConstraint("extra_runs >= 0", name="ck_delivery_extra_runs"),
        CheckConstraint(
            "(extra_type IS NULL AND extra_runs = 0) OR (extra_type IS NOT NULL)",
            name="ck_delivery_extra_consistency",
        ),
        CheckConstraint(
            "(wicket_type IS NULL AND dismissed_player_id IS NULL) OR "
            "(wicket_type IS NOT NULL)",
            name="ck_delivery_wicket_consistency",
        ),
        Index("ix_deliveries_innings_sequence", "innings_id", "sequence_number"),
        Index("ix_deliveries_innings_over", "innings_id", "over_number"),
        Index("ix_deliveries_bowler", "innings_id", "bowler_id"),
        Index("ix_deliveries_striker", "innings_id", "striker_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    innings_id: Mapped[int] = mapped_column(
        ForeignKey("innings.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Monotonic ball order across the entire innings.",
    )
    over_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0-based over index within the innings.",
    )
    delivery_in_over: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-based slot within the over; unique per innings+over.",
    )
    legal_ball_in_over: Mapped[int | None] = mapped_column(
        Integer,
        doc="1–6 for legal balls; NULL for wide/no-ball.",
    )
    is_legal_delivery: Mapped[bool] = mapped_column(Boolean, nullable=False)

    striker_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    non_striker_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    bowler_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)

    runs_off_bat: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_type: Mapped[ExtraType | None] = mapped_column(
        Enum(ExtraType, name="extra_type", native_enum=False),
    )
    extra_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    wicket_type: Mapped[WicketType | None] = mapped_column(
        Enum(WicketType, name="wicket_type", native_enum=False),
    )
    dismissed_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    fielder_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))

    innings: Mapped[Innings] = relationship(back_populates="deliveries")
    striker: Mapped[Player] = relationship(
        foreign_keys=[striker_id],
        back_populates="striker_deliveries",
    )
    non_striker: Mapped[Player] = relationship(foreign_keys=[non_striker_id])
    bowler: Mapped[Player] = relationship(
        foreign_keys=[bowler_id],
        back_populates="bowler_deliveries",
    )
    dismissed_player: Mapped[Player | None] = relationship(
        foreign_keys=[dismissed_player_id],
        back_populates="dismissals",
    )
    fielder: Mapped[Player | None] = relationship(
        foreign_keys=[fielder_id],
        back_populates="fielding_dismissals",
    )

    @property
    def total_runs(self) -> int:
        return self.runs_off_bat + self.extra_runs

    @classmethod
    def compute_is_legal(cls, extra_type: ExtraType | None) -> bool:
        return is_legal_delivery_extra(extra_type)

    @classmethod
    def next_legal_ball_in_over(cls, legal_balls_in_current_over: int) -> int | None:
        """Returns 1–6, or None if the over is already complete (6 legal balls)."""
        if legal_balls_in_current_over >= LEGAL_BALLS_PER_OVER:
            return None
        return legal_balls_in_current_over + 1
