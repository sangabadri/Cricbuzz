from sqlalchemy import Column, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base

class Squad(Base):
    __tablename__ = "squads"
    
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    captain_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    wicket_keeper_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    
    match_obj = relationship("Match", lazy="selectin")
    team_obj = relationship("Team", lazy="selectin")
    captain_obj = relationship("Player", foreign_keys=[captain_id], lazy="selectin")
    wicket_keeper_obj = relationship("Player", foreign_keys=[wicket_keeper_id], lazy="selectin")
    players = relationship("SquadPlayer", back_populates="squad", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("match_id", "team_id", name="unique_match_team_squad"),
    )


class SquadPlayer(Base):
    __tablename__ = "squad_players"
    
    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    is_playing_xi = Column(Boolean, nullable=False)
    
    squad = relationship("Squad", back_populates="players")
    player_obj = relationship("Player", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("squad_id", "player_id", name="unique_squad_player"),
    )