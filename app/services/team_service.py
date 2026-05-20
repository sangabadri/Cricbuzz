from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team


async def get_or_create_team(session: AsyncSession, name: str) -> Team:
    result = await session.execute(select(Team).where(Team.name == name))
    team = result.scalar_one_or_none()
    if team is not None:
        return team
    team = Team(name=name)
    session.add(team)
    await session.flush()
    return team
