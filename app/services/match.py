from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import aliased, selectinload

from app.database import get_db

from app.models.match import Match
from app.models.team import Team
from app.models.squad import Squad, SquadPlayer
from app.models.innings import Innings
from app.schemas.match import MatchCreate, MatchToss
from app.schemas.enums import MatchStatus, TossDecision, InningsStatus
from app.services.util import validate_none, raise_exception

IST = ZoneInfo("Asia/Kolkata")

class MatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def check_match_has_team(self, match: Match, team_id: int):
        if match.team_a != team_id and match.team_b != team_id:
            raise_exception(404, f"Match {match.id} doesn't have team {team_id}")

    def _enrich_match(self, match: Match) -> Match:
        if match.team_a_obj:
            match.team_a_name = match.team_a_obj.name
        if match.team_b_obj:
            match.team_b_name = match.team_b_obj.name
        if match.winner_obj:
            match.winner_name = match.winner_obj.name
        return match

    async def get_match(self, match_id: int) -> Match:
        result = await self.db.execute(
            select(Match)
            .options(
                selectinload(Match.team_a_obj),
                selectinload(Match.team_b_obj),
                selectinload(Match.winner_obj),
            )
            .where(Match.id == match_id)
        )
        match = result.scalar_one_or_none()
        validate_none(match, "Match")
        return self._enrich_match(match)

    async def list_matches(
        self,
        status: MatchStatus | None = None,
        search: str | None = None,
        team_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Match]:
        query = select(Match).options(
            selectinload(Match.team_a_obj),
            selectinload(Match.team_b_obj),
            selectinload(Match.winner_obj),
        )

        if status is not None:
            query = query.where(Match.status == status)

        if search:
            team_a_alias = aliased(Team)
            team_b_alias = aliased(Team)
            query = (
                query
                .outerjoin(team_a_alias, Match.team_a == team_a_alias.id)
                .outerjoin(team_b_alias, Match.team_b == team_b_alias.id)
                .where(
                    team_a_alias.name.ilike(f"%{search}%") |
                    team_b_alias.name.ilike(f"%{search}%") |
                    Match.venue.ilike(f"%{search}%")
                )
            )
        elif team_id is not None:
            query = query.where((Match.team_a == team_id) | (Match.team_b == team_id))

        query = query.order_by(Match.match_date.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        matches = result.scalars().all()
        return [self._enrich_match(m) for m in matches]

    async def create_match(self, match_in: MatchCreate) -> Match:
        if match_in.team_a == match_in.team_b:
            raise_exception(400, "Both teams cannot be same")
        match_dt = match_in.match_date if match_in.match_date.tzinfo else match_in.match_date.replace(tzinfo=IST)
        if match_dt <= datetime.now(IST):
            raise_exception(400, "Cannot create a match in the past")

        result = await self.db.execute(
            select(Team).where(Team.id.in_([match_in.team_a, match_in.team_b]))
        )
        teams = {team.id: team for team in result.scalars().all()}
        validate_none(teams.get(match_in.team_a), "Team A")
        validate_none(teams.get(match_in.team_b), "Team B")

        db_match = Match(
            team_a=match_in.team_a,
            team_b=match_in.team_b,
            venue=match_in.venue,
            match_date=match_in.match_date,
            format=match_in.format,
            status=MatchStatus.SCHEDULED,
        )
        self.db.add(db_match)
        await self.db.commit()
        return await self.get_match(db_match.id)

    async def conduct_toss(self, match_id: int, toss: MatchToss) -> Match:
        match = await self.get_match(match_id)

        # Idempotency: if exact toss already recorded, return current state safely
        if (
            match.status == MatchStatus.TOSS_DONE
            and match.toss_winner == toss.toss_winner
            and match.toss_decision == toss.toss_decision
        ):
            return match

        if match.status != MatchStatus.SCHEDULED:
            raise_exception(400, "Toss has already been conducted for this match")
        if toss.toss_winner != match.team_a and toss.toss_winner != match.team_b:
            raise_exception(400, f"Toss winner must be either team {match.team_a} or team {match.team_b}")

        squad_res = await self.db.execute(
            select(Squad.team_id).where(Squad.match_id == match.id)
        )
        squad_teams = set(squad_res.scalars().all())
        if match.team_a not in squad_teams or match.team_b not in squad_teams:
            raise_exception(400, "Both teams must have submitted squads before toss")

        other_team = match.team_b if toss.toss_winner == match.team_a else match.team_a
        if toss.toss_decision == TossDecision.BAT:
            inn1_batting = toss.toss_winner
            inn2_batting = other_team
        else:
            inn1_batting = other_team
            inn2_batting = toss.toss_winner

        innings_pairs = [
            (1, inn1_batting, inn2_batting),
            (2, inn2_batting, inn1_batting),
        ]

        match.toss_winner = toss.toss_winner
        match.toss_decision = toss.toss_decision
        match.status = MatchStatus.TOSS_DONE

        result = await self.db.execute(
            select(Innings).where(Innings.match_id == match.id).order_by(Innings.innings_number)
        )
        existing_innings = {inn.innings_number: inn for inn in result.scalars().all()}

        for num, batting_id, bowling_id in innings_pairs:
            if num in existing_innings:
                existing_innings[num].batting_team_id = batting_id
                existing_innings[num].bowling_team_id = bowling_id
            else:
                self.db.add(
                    Innings(
                        match_id=match.id,
                        innings_number=num,
                        batting_team_id=batting_id,
                        bowling_team_id=bowling_id,
                        status=InningsStatus.NOT_STARTED,
                    )
                )

        await self.db.commit()
        return await self.get_match(match.id)

    async def award_man_of_the_match(self, match_id: int, player_id: int) -> Match:
        match = await self.get_match(match_id)
        if match.status != MatchStatus.COMPLETED:
            raise_exception(400, f"Cannot award Man of the Match when match status is '{match.status.value}'")

        squad_res = await self.db.execute(
            select(SquadPlayer.player_id)
            .join(Squad, Squad.id == SquadPlayer.squad_id)
            .where(Squad.match_id == match_id, SquadPlayer.is_playing_xi == True)
        )
        playing_xi_pids = set(squad_res.scalars().all())
        if player_id not in playing_xi_pids:
            raise_exception(400, f"Player {player_id} is not in the Playing XI of either team for this match")

        match.mom = player_id
        await self.db.commit()
        return await self.get_match(match.id)

    async def abandon_match(self, match_id: int) -> Match:
        match = await self.get_match(match_id)
        if match.status == MatchStatus.COMPLETED:
            raise_exception(400, "Cannot abandon a completed match")
        if match.status == MatchStatus.ABANDONED:
            raise_exception(400, "Match is already abandoned")

        match.status = MatchStatus.ABANDONED
        await self.db.commit()
        return await self.get_match(match.id)


# Dependency helper
def get_match_service(db: AsyncSession = Depends(get_db)) -> MatchService:
    return MatchService(db)

# Backward-compatible function wrappers
async def validate_match(match_in: MatchCreate, db: AsyncSession):
    pass

async def create_match(match_in: MatchCreate, db: AsyncSession) -> Match:
    return await MatchService(db).create_match(match_in)

def check_match_has_team(match: Match, team_id: int):
    if match.team_a != team_id and match.team_b != team_id:
        raise_exception(404, f"Match {match.id} doesn't have team {team_id}")

async def get_match(match_id: int, db: AsyncSession) -> Match:
    return await MatchService(db).get_match(match_id)

async def handle_toss(match_id: int, toss: MatchToss, db: AsyncSession) -> Match:
    return await MatchService(db).conduct_toss(match_id, toss)

async def set_man_of_the_match(match_id: int, player_id: int, db: AsyncSession) -> Match:
    return await MatchService(db).award_man_of_the_match(match_id, player_id)

async def list_matches(status: MatchStatus | None, team_id: int | None, db: AsyncSession, limit: int = 20, offset: int = 0):
    return await MatchService(db).list_matches(status=status, team_id=team_id, limit=limit, offset=offset)

async def abandon_match(match_id: int, db: AsyncSession) -> Match:
    return await MatchService(db).abandon_match(match_id)