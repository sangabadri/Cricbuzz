from sqlalchemy import Column, Integer, ForeignKey, Enum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.schemas.enums import InningsStatus

class Innings(Base):
    __tablename__ = "innings"
    
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    innings_number = Column(Integer, nullable=False)
    batting_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    bowling_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    status = Column(Enum(InningsStatus), nullable=False, default=InningsStatus.NOT_STARTED)
    target = Column(Integer, nullable=True)

    match_obj = relationship("Match", back_populates="innings", lazy="selectin")
    batting_team_obj = relationship("Team", foreign_keys=[batting_team_id], lazy="selectin")
    bowling_team_obj = relationship("Team", foreign_keys=[bowling_team_id], lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "batting_team_id != bowling_team_id",
            name="batting_and_bowling_teams_must_be_different"
        ),
        CheckConstraint(
            "innings_number >= 1 AND innings_number <= 2",
            name="valid_innings_number"
        ),
        UniqueConstraint(
            "match_id", "innings_number",
            name="unique_match_innings"
        ),
    )
