from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.stats import (
    BatsmanCardResponse,
    BowlerFiguresResponse,
    HeadToHeadResponse,
    LiveScorecardResponse,
    MatchSummaryResponse,
    PartnershipTrackerResponse,
)
from app.services import stats_service

router = APIRouter()


@router.get(
    "/matches/{match_id}/scorecard",
    response_model=LiveScorecardResponse,
)
async def live_scorecard(
    match_id: int,
    innings_number: int | None = Query(
        default=None,
        ge=1,
        le=4,
        description="Omit to use the current (in-progress) innings.",
    ),
    session: AsyncSession = Depends(get_async_session),
) -> LiveScorecardResponse:
    return await stats_service.get_live_scorecard(session, match_id, innings_number)


@router.get(
    "/innings/{innings_id}/batsmen",
    response_model=BatsmanCardResponse,
)
async def batsman_card(
    innings_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> BatsmanCardResponse:
    return await stats_service.get_batsman_card(session, innings_id)


@router.get(
    "/innings/{innings_id}/bowlers",
    response_model=BowlerFiguresResponse,
)
async def bowler_figures(
    innings_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> BowlerFiguresResponse:
    return await stats_service.get_bowler_figures(session, innings_id)


@router.get(
    "/innings/{innings_id}/partnerships",
    response_model=PartnershipTrackerResponse,
)
async def partnership_tracker(
    innings_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> PartnershipTrackerResponse:
    return await stats_service.get_partnership_tracker(session, innings_id)


@router.get(
    "/matches/{match_id}/summary",
    response_model=MatchSummaryResponse,
)
async def match_summary(
    match_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> MatchSummaryResponse:
    return await stats_service.get_match_summary(session, match_id)


@router.get(
    "/teams/head-to-head",
    response_model=HeadToHeadResponse,
)
async def head_to_head(
    team_a_id: int = Query(..., description="First team id"),
    team_b_id: int = Query(..., description="Second team id"),
    session: AsyncSession = Depends(get_async_session),
) -> HeadToHeadResponse:
    return await stats_service.get_head_to_head(session, team_a_id, team_b_id)
