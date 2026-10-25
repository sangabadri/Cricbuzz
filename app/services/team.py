from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db

from app.models.team import Team
from app.models.match import Match
from app.schemas.enums import MatchStatus
from app.schemas.team import TeamCreate, TeamStatsResponse
from app.services.util import validate_none, validate_exists

class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_team(self, team_id: int) -> Team:
        team = await self.db.get(Team, team_id)
        validate_none(team, "Team")
        return team

    async def create_team(self, team_in: TeamCreate) -> Team:
        res = await self.db.execute(select(Team).where(Team.name == team_in.name))
        existing_team = res.scalar_one_or_none()
        validate_exists(existing_team, f"Team with name {team_in.name}")

        db_team = Team(name=team_in.name)
        self.db.add(db_team)
        await self.db.commit()
        await self.db.refresh(db_team)
        return db_team

    async def list_teams(
        self,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Team]:
        query = select(Team)
        if search:
            query = query.where(Team.name.ilike(f"%{search}%"))
        query = query.order_by(Team.name).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_team_stats(self, team_id: int) -> TeamStatsResponse:
        team = await self.get_team(team_id)

        res = await self.db.execute(
            select(Match)
            .where(
                ((Match.team_a == team_id) | (Match.team_b == team_id)),
                Match.status.in_([MatchStatus.COMPLETED, MatchStatus.ABANDONED])
            )
        )
        matches = res.scalars().all()

        matches_played = len(matches)
        matches_won = sum(1 for m in matches if m.winner == team_id)
        matches_lost = sum(1 for m in matches if m.status == MatchStatus.COMPLETED and m.winner is not None and m.winner != team_id)
        matches_abandoned = sum(1 for m in matches if m.status == MatchStatus.ABANDONED)
        win_pct = round((matches_won / matches_played) * 100.0, 2) if matches_played > 0 else 0.0

        return TeamStatsResponse(
            team_id=team.id,
            name=team.name,
            matches_played=matches_played,
            matches_won=matches_won,
            matches_lost=matches_lost,
            matches_abandoned=matches_abandoned,
            win_percentage=win_pct,
        )


# Dependency helper
def get_team_service(db: AsyncSession = Depends(get_db)) -> TeamService:
    return TeamService(db)

# Backward-compatible function wrappers
async def create_team(team_in: TeamCreate, db: AsyncSession) -> Team:
    return await TeamService(db).create_team(team_in)

async def get_team(team_id: int, db: AsyncSession) -> Team:
    return await TeamService(db).get_team(team_id)

async def list_teams(search: str | None, db: AsyncSession, limit: int = 20, offset: int = 0):
    return await TeamService(db).list_teams(search=search, limit=limit, offset=offset)

async def get_team_stats(team_id: int, db: AsyncSession) -> TeamStatsResponse:
    return await TeamService(db).get_team_stats(team_id)