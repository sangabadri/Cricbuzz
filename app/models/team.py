from sqlalchemy import Column, String, Integer
from app.models.base import Base

class Team(Base):
    __tablename__="teams"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)