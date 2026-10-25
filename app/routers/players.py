from fastapi import APIRouter, Depends

from app.schemas.player import PlayerCreate, PlayerResponse, PlayerCareerStatsResponse
from app.schemas.enums import Role
from app.services.player import PlayerService, get_player_service

router = APIRouter(prefix="/players", tags=["Players"])

@router.get("/", response_model=list[PlayerResponse])
async def get_all_players(
    role: Role | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    service: PlayerService = Depends(get_player_service),
):
    return await service.list_players(role=role, search=search, limit=limit, offset=offset)

@router.get("/{player_id}", response_model=PlayerResponse)
async def get_player(
    player_id: int,
    service: PlayerService = Depends(get_player_service),
):
    return await service.get_player(player_id)

@router.get("/{player_id}/stats", response_model=PlayerCareerStatsResponse)
async def get_player_stats(
    player_id: int,
    service: PlayerService = Depends(get_player_service),
):
    return await service.get_player_career_stats(player_id)

@router.post("/", response_model=PlayerResponse)
async def create_player(
    player: PlayerCreate,
    service: PlayerService = Depends(get_player_service),
):
    return await service.create_player(player)