from fastapi import APIRouter, Depends

from app.schemas.match import MatchCreate, MatchResponse, MatchToss, MatchMOM
from app.schemas.enums import MatchStatus
from app.services.match import MatchService, get_match_service

router = APIRouter(prefix="/matches", tags=["Matches"])

@router.get("/", response_model=list[MatchResponse])
async def get_matches(
    status: MatchStatus | None = None,
    search: str | None = None,
    team_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
    service: MatchService = Depends(get_match_service),
):
    return await service.list_matches(
        status=status,
        search=search,
        team_id=team_id,
        limit=limit,
        offset=offset,
    )

@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: int,
    service: MatchService = Depends(get_match_service),
):
    return await service.get_match(match_id)

@router.post("/", response_model=MatchResponse)
async def create_match(
    match: MatchCreate,
    service: MatchService = Depends(get_match_service),
):
    return await service.create_match(match)

@router.post("/{match_id}/toss", response_model=MatchResponse)
async def conduct_toss(
    match_id: int,
    toss: MatchToss,
    service: MatchService = Depends(get_match_service),
):
    return await service.conduct_toss(match_id, toss)

@router.post("/{match_id}/mom", response_model=MatchResponse)
async def award_man_of_the_match(
    match_id: int,
    mom_data: MatchMOM,
    service: MatchService = Depends(get_match_service),
):
    return await service.award_man_of_the_match(match_id, mom_data.player_id)

@router.post("/{match_id}/abandon", response_model=MatchResponse)
async def abandon(
    match_id: int,
    service: MatchService = Depends(get_match_service),
):
    return await service.abandon_match(match_id)
