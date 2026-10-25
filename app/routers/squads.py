from fastapi import APIRouter, Depends

from app.schemas.squad import SquadCreate, SquadResponse
from app.services.squad import SquadService, get_squad_service
from app.services.util import validate_none

router = APIRouter(prefix="/matches", tags=["Squads"])

@router.get("/{match_id}/squad/{team_id}", response_model=SquadResponse)
async def get_squad(
    match_id: int,
    team_id: int,
    service: SquadService = Depends(get_squad_service),
):
    squad = await service.get_squad(match_id, team_id)
    validate_none(squad, f"Squad for (Match: {match_id}, Team: {team_id})")
    return squad

@router.post("/{match_id}/squad", response_model=SquadResponse)
async def create_squad(
    match_id: int,
    squad: SquadCreate,
    service: SquadService = Depends(get_squad_service),
):
    return await service.create_squad(match_id, squad)