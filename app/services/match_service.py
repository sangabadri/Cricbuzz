from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError
from app.models.enums import InningsStatus, MatchStatus
from app.models.innings import Innings
from app.models.match import Match
from app.models.team import Team
from app.schemas.match import CreateMatchRequest, InningsBrief, MatchResponse
from app.services.team_service import get_or_create_team


async def create_match(session: AsyncSession, payload: CreateMatchRequest) -> MatchResponse:
    if payload.team_a_name.strip().lower() == payload.team_b_name.strip().lower():
        raise ValidationError("team_a_name and team_b_name must be different")

    team_a = await get_or_create_team(session, payload.team_a_name.strip())
    team_b = await get_or_create_team(session, payload.team_b_name.strip())

    toss_winner_id: int | None = None
    if payload.toss_winner_team:
        toss_winner_id = (
            team_a.id
            if payload.toss_winner_team == payload.team_a_name
            else team_b.id
        )

    status = MatchStatus.SCHEDULED
    first_innings: Innings | None = None

    match = Match(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        venue=payload.venue.strip(),
        match_date=payload.match_date,
        format=payload.format,
        status=status,
        toss_winner_id=toss_winner_id,
        elected_to_bat_first=payload.elected_to_bat_first,
    )
    session.add(match)
    await session.flush()

    if payload.start_first_innings:
        if payload.elected_to_bat_first is None:
            raise ValidationError(
                "elected_to_bat_first is required when start_first_innings is true"
            )
        batting_team_id, bowling_team_id = _resolve_innings_teams(
            team_a.id,
            team_b.id,
            toss_winner_id,
            payload.elected_to_bat_first,
        )
        caps = Innings.caps_from_match_format(payload.format)
        first_innings = Innings(
            match_id=match.id,
            innings_number=1,
            batting_team_id=batting_team_id,
            bowling_team_id=bowling_team_id,
            status=InningsStatus.IN_PROGRESS,
            **caps,
        )
        session.add(first_innings)
        match.status = MatchStatus.LIVE
        await session.flush()

    await session.refresh(match, ["team_a", "team_b"])

    return MatchResponse(
        id=match.id,
        venue=match.venue,
        match_date=match.match_date,
        format=match.format,
        status=match.status,
        team_a=match.team_a,
        team_b=match.team_b,
        toss_winner_id=match.toss_winner_id,
        elected_to_bat_first=match.elected_to_bat_first,
        first_innings=(
            InningsBrief.model_validate(first_innings) if first_innings else None
        ),
    )


def _resolve_innings_teams(
    team_a_id: int,
    team_b_id: int,
    toss_winner_id: int | None,
    elected_to_bat_first: bool,
) -> tuple[int, int]:
    if toss_winner_id is None:
        raise ValidationError("toss_winner_team is required to start the first innings")

    other_team_id = team_b_id if toss_winner_id == team_a_id else team_a_id
    if elected_to_bat_first:
        batting_team_id = toss_winner_id
        bowling_team_id = other_team_id
    else:
        batting_team_id = other_team_id
        bowling_team_id = toss_winner_id
    return batting_team_id, bowling_team_id


async def get_match(session: AsyncSession, match_id: int) -> Match:
    result = await session.execute(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.team_a), selectinload(Match.team_b))
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise NotFoundError(f"Match {match_id} not found")
    return match
