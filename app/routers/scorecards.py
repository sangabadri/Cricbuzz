from fastapi import APIRouter, Depends

from app.schemas.scorecard import MatchScorecardResponse, InningsScorecard, LiveMatchResponse
from app.services.scorecard import ScorecardService, get_scorecard_service

router = APIRouter(prefix="/matches", tags=["Scorecard"])


@router.get("/{match_id}/live", response_model=LiveMatchResponse)
async def get_live_ticker(
    match_id: int,
    service: ScorecardService = Depends(get_scorecard_service),
):
    return await service.get_live_match_state(match_id)


@router.get("/{match_id}/scorecard", response_model=MatchScorecardResponse)
async def get_scorecard(
    match_id: int,
    service: ScorecardService = Depends(get_scorecard_service),
):
    return await service.get_match_scorecard(match_id)


@router.get("/{match_id}/innings/{innings_number}/scorecard", response_model=InningsScorecard)
async def get_single_innings_scorecard(
    match_id: int,
    innings_number: int,
    service: ScorecardService = Depends(get_scorecard_service),
):
    return await service.get_innings_scorecard(match_id, innings_number)
