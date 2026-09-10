from sqlalchemy.orm import Session

from app.models.team import Team
from app.services.util import validate_none

def get_team(team_id : int, db : Session):
    team = db.get(Team, team_id)
    validate_none(team, "Team")
    return team