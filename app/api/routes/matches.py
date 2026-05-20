from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.match import CreateMatchRequest, MatchResponse
from app.services import match_service

router = APIRouter(prefix="/matches")


@router.post("", response_model=MatchResponse, status_code=201)
async def create_match(
    payload: CreateMatchRequest,
    session: AsyncSession = Depends(get_async_session),
) -> MatchResponse:
    """Create a match (and optionally the first innings after the toss)."""
    return await match_service.create_match(session, payload)
