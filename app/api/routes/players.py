from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.player import (
    AddPlayersRequest,
    AddPlayersResponse,
    PlayerCreate,
    PlayerResponse,
)
from app.services import player_service

router = APIRouter()


@router.post("/players", response_model=PlayerResponse, status_code=201)
async def create_player(
    payload: PlayerCreate,
    session: AsyncSession = Depends(get_async_session),
) -> PlayerResponse:
    """Register a player in the global player pool."""
    return await player_service.create_player(session, payload)


@router.post(
    "/matches/{match_id}/players",
    response_model=AddPlayersResponse,
    status_code=201,
)
async def add_players_to_match(
    match_id: int,
    payload: AddPlayersRequest,
    session: AsyncSession = Depends(get_async_session),
) -> AddPlayersResponse:
    """Add one or more players to a match squad / playing XI."""
    return await player_service.add_players_to_match(session, match_id, payload)
