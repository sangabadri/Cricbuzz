from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    LEGAL_BALLS_PER_OVER,
    InningsStatus,
    format_bowler_over_cap,
    format_innings_over_cap,
)

if TYPE_CHECKING:
    from app.models.delivery import Delivery
    from app.models.enums import MatchFormat
    from app.models.match import Match
    from app.models.team import Team


class Innings(Base):
    """
    One batting innings within a match.
    Denormalized counters support fast live scorecards; they are updated when
    deliveries are recorded. `legal_balls_bowled` counts only legal deliveries
    (excludes wides and no-balls).
    """

    __tablename__ = "innings"
    __table_args__ = (
        UniqueConstraint("match_id", "innings_number", name="uq_innings_match_number"),
        CheckConstraint("innings_number >= 1 AND innings_number <= 4", name="ck_innings_number"),
        CheckConstraint("total_wickets >= 0 AND total_wickets <= 10", name="ck_innings_wickets"),
        CheckConstraint("legal_balls_bowled >= 0", name="ck_innings_legal_balls"),
        CheckConstraint("target_runs IS NULL OR target_runs > 0", name="ck_innings_target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    innings_number: Mapped[int] = mapped_column(Integer, nullable=False)
    batting_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    bowling_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    status: Mapped[InningsStatus] = mapped_column(
        Enum(InningsStatus, name="innings_status", native_enum=False),
        nullable=False,
        default=InningsStatus.NOT_STARTED,
        server_default=InningsStatus.NOT_STARTED.value,
    )

    # Format-derived caps copied at innings creation for stable historical rules.
    max_overs: Mapped[int | None] = mapped_column(Integer)
    max_wickets: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        server_default="10",
    )
    max_bowler_overs: Mapped[int | None] = mapped_column(Integer)

    total_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_wickets: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    legal_balls_bowled: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    extras_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    target_runs: Mapped[int | None] = mapped_column(Integer)

    match: Mapped[Match] = relationship(back_populates="innings")
    batting_team: Mapped[Team] = relationship(foreign_keys=[batting_team_id])
    bowling_team: Mapped[Team] = relationship(foreign_keys=[bowling_team_id])
    deliveries: Mapped[list[Delivery]] = relationship(
        back_populates="innings",
        cascade="all, delete-orphan",
        order_by="Delivery.sequence_number",
    )

    @classmethod
    def caps_from_match_format(cls, match_format: "MatchFormat") -> dict:
        return {
            "max_overs": format_innings_over_cap(match_format),
            "max_wickets": 10,
            "max_bowler_overs": format_bowler_over_cap(match_format),
        }

    @property
    def overs_completed(self) -> int:
        return self.legal_balls_bowled // LEGAL_BALLS_PER_OVER

    @property
    def balls_in_current_over(self) -> int:
        return self.legal_balls_bowled % LEGAL_BALLS_PER_OVER

    @property
    def overs_display(self) -> str:
        completed = self.overs_completed
        balls = self.balls_in_current_over
        return f"{completed}.{balls}"

    @property
    def is_innings_complete(self) -> bool:
        if self.status in (InningsStatus.COMPLETED, InningsStatus.DECLARED):
            return True
        if self.total_wickets >= self.max_wickets:
            return True
        if self.max_overs is not None and self.legal_balls_bowled >= self.max_overs * LEGAL_BALLS_PER_OVER:
            return True
        return False
