from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.match import Match
from app.models.match_roster import MatchRoster
from app.models.player import Player
from app.schemas.player import (
    AddPlayersRequest,
    AddPlayersResponse,
    PlayerCreate,
    PlayerResponse,
    RosterPlayerCreate,
)
from app.services.match_service import get_match


async def create_player(session: AsyncSession, payload: PlayerCreate) -> PlayerResponse:
    player = Player(
        name=payload.name.strip(),
        role=payload.role,
        batting_style=payload.batting_style,
        bowling_style=payload.bowling_style,
    )
    session.add(player)
    await session.flush()
    return PlayerResponse.model_validate(player)


async def add_players_to_match(
    session: AsyncSession,
    match_id: int,
    payload: AddPlayersRequest,
) -> AddPlayersResponse:
    match = await get_match(session, match_id)

    if payload.team_id not in (match.team_a_id, match.team_b_id):
        raise ValidationError(
            f"team_id {payload.team_id} is not part of match {match_id}"
        )

    entries: list[MatchRoster] = []
    for item in payload.players:
        player = await _resolve_player(session, item)
        existing = await session.execute(
            select(MatchRoster).where(
                MatchRoster.match_id == match_id,
                MatchRoster.player_id == player.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                f"Player {player.id} is already on the roster for match {match_id}"
            )

        roster = MatchRoster(
            match_id=match_id,
            team_id=payload.team_id,
            player_id=player.id,
            squad_role=item.squad_role,
            is_playing_xi=item.is_playing_xi,
            is_captain=item.is_captain,
            is_wicketkeeper=item.is_wicketkeeper,
        )
        session.add(roster)
        entries.append(roster)

    await session.flush()

    result = await session.execute(
        select(MatchRoster)
        .where(MatchRoster.id.in_([e.id for e in entries]))
        .options(selectinload(MatchRoster.player))
    )
    loaded = list(result.scalars().all())
    return AddPlayersResponse(roster_entries=loaded)


async def _resolve_player(session: AsyncSession, item: RosterPlayerCreate) -> Player:
    if item.player_id is not None:
        result = await session.execute(select(Player).where(Player.id == item.player_id))
        player = result.scalar_one_or_none()
        if player is None:
            raise NotFoundError(f"Player {item.player_id} not found")
        return player

    if not item.name or not item.role:
        raise ValidationError(
            "Each roster entry must provide player_id or both name and role"
        )

    player = Player(
        name=item.name.strip(),
        role=item.role,
        batting_style=item.batting_style,
        bowling_style=item.bowling_style,
    )
    session.add(player)
    await session.flush()
    return player
