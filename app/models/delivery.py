from sqlalchemy import Column, Integer, String, ForeignKey, Enum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.schemas.enums import ExtraType, WicketType

class Delivery(Base):
    __tablename__ = "deliveries"
    
    id = Column(Integer, primary_key=True)
    innings_id = Column(Integer, ForeignKey("innings.id"), nullable=False)
    over = Column(Integer, nullable=False)
    ball = Column(Integer, nullable=False)
    bowler_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    batsman_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    non_striker_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    runs = Column(Integer, nullable=False, default=0)
    extra_type = Column(Enum(ExtraType), nullable=True)
    extras = Column(Integer, nullable=False, default=0)
    wicket_type = Column(Enum(WicketType), nullable=True)
    player_out_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    fielder_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    commentary = Column(String, nullable=True)
    
    innings_obj = relationship("Innings", lazy="selectin")
    bowler_obj = relationship("Player", foreign_keys=[bowler_id], lazy="selectin")
    batsman_obj = relationship("Player", foreign_keys=[batsman_id], lazy="selectin")
    non_striker_obj = relationship("Player", foreign_keys=[non_striker_id], lazy="selectin")
    player_out_obj = relationship("Player", foreign_keys=[player_out_id], lazy="selectin")
    fielder_obj = relationship("Player", foreign_keys=[fielder_id], lazy="selectin")

    __table_args__ = (
        CheckConstraint("runs >= 0 AND runs <= 6", name="valid_runs_range"),
        CheckConstraint("extras >= 0", name="valid_extras_range"),
        CheckConstraint("over >= 0", name="valid_over_number"),
        CheckConstraint("ball >= 1", name="valid_ball_number"),
        CheckConstraint("batsman_id != non_striker_id", name="batsman_and_non_striker_must_differ"),
        CheckConstraint("batsman_id != bowler_id", name="batsman_and_bowler_must_differ"),
        UniqueConstraint("innings_id", "over", "ball", name="unique_ball_in_over"),
    )
