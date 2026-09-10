from sqlalchemy import Column, Integer, String, Enum
from app.models.base import Base
from app.schemas.enums import Role, BattingStyle, BowlingStyle

class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    role = Column(Enum(Role), nullable=False)
    batting = Column(Enum(BattingStyle), nullable=False)
    bowling = Column(Enum(BowlingStyle), nullable=True)