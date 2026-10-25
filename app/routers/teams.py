from fastapi import APIRouter, Depends

from app.schemas.team import TeamCreate, TeamResponse, TeamStatsResponse
from app.services.team import TeamService, get_team_service

router = APIRouter(prefix="/team", tags=["Teams"])

@router.get("/", response_model=list[TeamResponse])
async def get_all_teams(
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    service: TeamService = Depends(get_team_service),
):
    return await service.list_teams(search=search, limit=limit, offset=offset)

@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: int,
    service: TeamService = Depends(get_team_service),
):
    return await service.get_team(team_id)

@router.get("/{team_id}/stats", response_model=TeamStatsResponse)
async def get_team_statistics(
    team_id: int,
    service: TeamService = Depends(get_team_service),
):
    return await service.get_team_stats(team_id)

@router.post("/", response_model=TeamResponse)
async def create_team(
    team: TeamCreate,
    service: TeamService = Depends(get_team_service),
):
    return await service.create_team(team)