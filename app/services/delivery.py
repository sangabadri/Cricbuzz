from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.match import Match
from app.models.innings import Innings
from app.models.delivery import Delivery
from app.models.squad import Squad, SquadPlayer
from app.models.player import Player
from app.schemas.delivery import DeliveryCreate
from app.schemas.enums import MatchStatus, InningsStatus, ExtraType, WicketType
from app.services.util import validate_none, raise_exception

from app.domain.formats import get_format_rules
from app.domain.over import BallEvent
from app.domain.innings import InningsAggregate
from app.domain.exceptions import CricketDomainError


def delivery_to_ball_event(d: Delivery) -> BallEvent:
    return BallEvent(
        over=d.over,
        ball=d.ball,
        bowler_id=d.bowler_id,
        batsman_id=d.batsman_id,
        non_striker_id=d.non_striker_id,
        runs=d.runs,
        extra_type=d.extra_type,
        extras=d.extras,
        wicket_type=d.wicket_type,
        player_out_id=d.player_out_id,
        fielder_id=d.fielder_id,
        commentary=d.commentary,
    )


def hydrate_innings_aggregate(
    innings: Innings,
    match: Match,
    deliveries: list[Delivery],
) -> InningsAggregate:
    rules = get_format_rules(match.format)
    ball_events = [delivery_to_ball_event(d) for d in deliveries]
    return InningsAggregate(
        innings_number=innings.innings_number,
        batting_team_id=innings.batting_team_id,
        bowling_team_id=innings.bowling_team_id,
        format_rules=rules,
        target=innings.target,
        status=innings.status,
        balls=ball_events,
    )


class DeliveryRuleValidator:
    """Encapsulates validation rules for delivery payload and playing squad membership."""

    @staticmethod
    def validate_payload(delivery: DeliveryCreate):
        if delivery.runs < 0 or delivery.runs > 6:
            raise_exception(400, "Runs must be between 0 and 6")
        if delivery.extras < 0:
            raise_exception(400, "Extras cannot be negative")
        if delivery.batsman_id == delivery.non_striker_id:
            raise_exception(400, "Striker and non-striker cannot be the same player")
        if delivery.batsman_id == delivery.bowler_id:
            raise_exception(400, "Batsman and bowler cannot be the same player")
        if delivery.extra_type in (ExtraType.WIDE, ExtraType.NOBALL) and delivery.extras < 1:
            raise_exception(400, f"Extras must be at least 1 for {delivery.extra_type.value}")
        if delivery.extra_type is None and delivery.extras != 0:
            raise_exception(400, "Extras must be 0 when extra_type is None")

        if delivery.wicket_type is None:
            if delivery.player_out_id is not None:
                raise_exception(400, "player_out_id must be None when no wicket falls")
            if delivery.fielder_id is not None:
                raise_exception(400, "fielder_id must be None when no wicket falls")
        else:
            if delivery.player_out_id is None:
                raise_exception(400, "player_out_id is required when a wicket falls")
            if delivery.player_out_id not in (delivery.batsman_id, delivery.non_striker_id):
                raise_exception(400, "player_out_id must be either striker or non-striker")
            if delivery.wicket_type in (
                WicketType.BOWLED,
                WicketType.LBW,
                WicketType.HIT_WICKET,
                WicketType.CAUGHT,
                WicketType.STUMPED,
                WicketType.CAUGHT_AND_BOWLED,
            ):
                if delivery.player_out_id != delivery.batsman_id:
                    raise_exception(400, f"Only striker can be dismissed {delivery.wicket_type.value}")
            if delivery.wicket_type in (
                WicketType.BOWLED,
                WicketType.LBW,
                WicketType.HIT_WICKET,
                WicketType.CAUGHT_AND_BOWLED,
            ):
                if delivery.fielder_id is not None:
                    raise_exception(400, f"fielder_id must be None when wicket is {delivery.wicket_type.value}")
            elif delivery.wicket_type in (WicketType.CAUGHT, WicketType.RUN_OUT):
                if delivery.fielder_id is None:
                    raise_exception(400, f"fielder_id is required when wicket is {delivery.wicket_type.value}")
                if delivery.wicket_type == WicketType.CAUGHT and delivery.fielder_id == delivery.bowler_id:
                    raise_exception(400, "fielder_id cannot be the bowler for caught dismissal (use caught_and_bowled)")

    @staticmethod
    def validate_playing_xis(
        delivery: DeliveryCreate,
        batting_xi: set[int],
        bowling_xi: set[int],
        bowling_styles: dict[int, object],
        bowling_wicket_keeper_id: int | None = None,
    ):
        if delivery.batsman_id not in batting_xi:
            raise_exception(400, f"Batsman {delivery.batsman_id} is not in batting team's playing XI")
        if delivery.non_striker_id not in batting_xi:
            raise_exception(400, f"Non-striker {delivery.non_striker_id} is not in batting team's playing XI")
        if delivery.bowler_id not in bowling_xi:
            raise_exception(400, f"Bowler {delivery.bowler_id} is not in bowling team's playing XI")
        if bowling_styles.get(delivery.bowler_id) is None:
            raise_exception(400, f"Player {delivery.bowler_id} cannot bowl because they do not have a bowling style")
        if delivery.fielder_id is not None and delivery.fielder_id not in bowling_xi:
            raise_exception(400, f"Fielder {delivery.fielder_id} is not in bowling team's playing XI")
        if delivery.wicket_type == WicketType.STUMPED and delivery.fielder_id is not None:
            if delivery.fielder_id != bowling_wicket_keeper_id:
                raise_exception(400, f"Player {delivery.fielder_id} is not the designated wicket-keeper")


class DeliveryService:
    """Coordinates delivery recording, edits, undo operations, and match state queries via InningsAggregate."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_and_lock_innings(self, match_id: int, innings_number: int) -> Innings:
        result = await self.db.execute(
            select(Innings)
            .where(Innings.match_id == match_id, Innings.innings_number == innings_number)
            .with_for_update()
        )
        innings = result.scalar_one_or_none()
        validate_none(innings, f"Innings {innings_number} for Match {match_id}")
        return innings

    async def _get_squad_context(self, match_id: int, innings: Innings):
        squad_res = await self.db.execute(
            select(SquadPlayer.player_id, Squad.team_id, Squad.wicket_keeper_id, Player.bowling)
            .join(Squad, Squad.id == SquadPlayer.squad_id)
            .join(Player, Player.id == SquadPlayer.player_id)
            .where(Squad.match_id == match_id, SquadPlayer.is_playing_xi == True)
        )
        squad_rows = squad_res.all()
        batting_xi = {r.player_id for r in squad_rows if r.team_id == innings.batting_team_id}
        bowling_xi = {r.player_id for r in squad_rows if r.team_id == innings.bowling_team_id}
        bowling_styles = {r.player_id: r.bowling for r in squad_rows if r.team_id == innings.bowling_team_id}
        bowling_wicket_keeper_id = next(
            (r.wicket_keeper_id for r in squad_rows if r.team_id == innings.bowling_team_id),
            None,
        )
        return batting_xi, bowling_xi, bowling_styles, bowling_wicket_keeper_id

    async def get_innings_deliveries(self, match_id: int, innings_number: int) -> list[Delivery]:
        inn_res = await self.db.execute(
            select(Innings.id).where(Innings.match_id == match_id, Innings.innings_number == innings_number)
        )
        innings_id = inn_res.scalar_one_or_none()
        validate_none(innings_id, f"Innings {innings_number} for Match {match_id}")

        result = await self.db.execute(
            select(Delivery)
            .where(Delivery.innings_id == innings_id)
            .order_by(Delivery.over, Delivery.ball)
        )
        return result.scalars().all()

    async def _sync_match_state(self, aggregate: InningsAggregate, innings: Innings, match: Match):
        """Synchronizes database status columns with the pure aggregate state."""
        innings.status = aggregate.status

        if aggregate.is_target_reached:
            innings.status = InningsStatus.COMPLETED
            match.status = MatchStatus.COMPLETED
            match.winner = innings.batting_team_id
        elif aggregate.is_all_out or aggregate.is_max_overs_reached:
            innings.status = InningsStatus.COMPLETED
            if innings.innings_number == 1:
                inn2_res = await self.db.execute(
                    select(Innings).where(Innings.match_id == match.id, Innings.innings_number == 2)
                )
                inn2 = inn2_res.scalar_one_or_none()
                if inn2 and inn2.target != aggregate.total_runs + 1:
                    inn2.target = aggregate.total_runs + 1
                match.status = MatchStatus.INNINGS_BREAK
            elif innings.innings_number == 2:
                match.status = MatchStatus.COMPLETED
                target_winner = (
                    None
                    if (innings.target is not None and aggregate.total_runs == innings.target - 1)
                    else innings.bowling_team_id
                )
                match.winner = target_winner
        else:
            if not aggregate.balls:
                innings.status = InningsStatus.NOT_STARTED
                match.status = MatchStatus.TOSS_DONE if innings.innings_number == 1 else MatchStatus.INNINGS_BREAK
                match.winner = None
                if innings.innings_number == 1:
                    inn2_res = await self.db.execute(
                        select(Innings).where(Innings.match_id == match.id, Innings.innings_number == 2)
                    )
                    inn2 = inn2_res.scalar_one_or_none()
                    if inn2:
                        inn2.target = None
            else:
                innings.status = InningsStatus.IN_PROGRESS
                match.status = MatchStatus.LIVE
                match.winner = None
                if innings.innings_number == 1:
                    inn2_res = await self.db.execute(
                        select(Innings).where(Innings.match_id == match.id, Innings.innings_number == 2)
                    )
                    inn2 = inn2_res.scalar_one_or_none()
                    if inn2 and inn2.target is not None:
                        inn2.target = None

    async def record_delivery(
        self,
        match_id: int,
        innings_number: int,
        delivery_in: DeliveryCreate,
    ) -> Delivery:
        DeliveryRuleValidator.validate_payload(delivery_in)

        innings = await self.get_and_lock_innings(match_id, innings_number)
        match = innings.match_obj

        # Match status preconditions
        if match.status not in (MatchStatus.TOSS_DONE, MatchStatus.LIVE, MatchStatus.INNINGS_BREAK):
            raise_exception(400, f"Cannot bowl delivery in match with status '{match.status.value}'")
        if innings.status == InningsStatus.COMPLETED:
            raise_exception(400, f"Innings {innings.innings_number} is already completed")

        # Squad & Playing XI validation
        batting_xi, bowling_xi, bowling_styles, bowling_wicket_keeper_id = await self._get_squad_context(match_id, innings)
        DeliveryRuleValidator.validate_playing_xis(delivery_in, batting_xi, bowling_xi, bowling_styles, bowling_wicket_keeper_id)

        # Existing deliveries in innings
        deliv_res = await self.db.execute(
            select(Delivery)
            .where(Delivery.innings_id == innings.id)
            .order_by(Delivery.over, Delivery.ball)
        )
        all_deliveries = list(deliv_res.scalars().all())

        effective_fielder_id = delivery_in.fielder_id
        if delivery_in.wicket_type == WicketType.STUMPED and effective_fielder_id is None:
            effective_fielder_id = bowling_wicket_keeper_id

        # Hydrate aggregate and execute domain logic
        aggregate = hydrate_innings_aggregate(innings, match, all_deliveries)
        ball_event = BallEvent(
            over=delivery_in.over,
            ball=delivery_in.ball,
            bowler_id=delivery_in.bowler_id,
            batsman_id=delivery_in.batsman_id,
            non_striker_id=delivery_in.non_striker_id,
            runs=delivery_in.runs,
            extra_type=delivery_in.extra_type,
            extras=delivery_in.extras,
            wicket_type=delivery_in.wicket_type,
            player_out_id=delivery_in.player_out_id,
            fielder_id=effective_fielder_id,
            commentary=delivery_in.commentary,
        )

        try:
            aggregate.record_ball(ball_event)
        except CricketDomainError as e:
            raise_exception(400, str(e))

        db_delivery = Delivery(
            innings_id=innings.id,
            over=delivery_in.over,
            ball=delivery_in.ball,
            bowler_id=delivery_in.bowler_id,
            batsman_id=delivery_in.batsman_id,
            non_striker_id=delivery_in.non_striker_id,
            runs=delivery_in.runs,
            extra_type=delivery_in.extra_type,
            extras=delivery_in.extras,
            wicket_type=delivery_in.wicket_type,
            player_out_id=delivery_in.player_out_id,
            fielder_id=effective_fielder_id,
            commentary=delivery_in.commentary,
        )
        self.db.add(db_delivery)

        await self._sync_match_state(aggregate, innings, match)

        await self.db.commit()
        await self.db.refresh(db_delivery)
        return db_delivery

    async def update_last_delivery(
        self,
        match_id: int,
        innings_number: int,
        delivery_in: DeliveryCreate,
    ) -> Delivery:
        DeliveryRuleValidator.validate_payload(delivery_in)

        innings = await self.get_and_lock_innings(match_id, innings_number)
        match = innings.match_obj

        if match.status in (MatchStatus.COMPLETED, MatchStatus.ABANDONED):
            raise_exception(400, f"Cannot modify delivery for match with status '{match.status.value}'")
        if innings.status == InningsStatus.COMPLETED:
            raise_exception(400, "Cannot modify delivery for completed innings")

        batting_xi, bowling_xi, bowling_styles, bowling_wicket_keeper_id = await self._get_squad_context(match_id, innings)
        DeliveryRuleValidator.validate_playing_xis(delivery_in, batting_xi, bowling_xi, bowling_styles, bowling_wicket_keeper_id)

        deliv_res = await self.db.execute(
            select(Delivery)
            .where(Delivery.innings_id == innings.id)
            .order_by(Delivery.over, Delivery.ball)
        )
        all_deliveries = list(deliv_res.scalars().all())
        if not all_deliveries:
            raise_exception(404, "No deliveries found in this innings to update")

        last_delivery = all_deliveries[-1]
        if delivery_in.over != last_delivery.over:
            raise_exception(400, f"Cannot change over number. Expected over {last_delivery.over}")
        if delivery_in.ball != last_delivery.ball:
            raise_exception(400, f"Cannot change ball number. Expected ball {last_delivery.ball}")

        effective_fielder_id = delivery_in.fielder_id
        if delivery_in.wicket_type == WicketType.STUMPED and effective_fielder_id is None:
            effective_fielder_id = bowling_wicket_keeper_id

        # Hydrate aggregate with prior deliveries and record updated ball
        prior_deliveries = all_deliveries[:-1]
        aggregate = hydrate_innings_aggregate(innings, match, prior_deliveries)
        ball_event = BallEvent(
            over=delivery_in.over,
            ball=delivery_in.ball,
            bowler_id=delivery_in.bowler_id,
            batsman_id=delivery_in.batsman_id,
            non_striker_id=delivery_in.non_striker_id,
            runs=delivery_in.runs,
            extra_type=delivery_in.extra_type,
            extras=delivery_in.extras,
            wicket_type=delivery_in.wicket_type,
            player_out_id=delivery_in.player_out_id,
            fielder_id=effective_fielder_id,
            commentary=delivery_in.commentary,
        )

        try:
            aggregate.record_ball(ball_event)
        except CricketDomainError as e:
            raise_exception(400, str(e))

        last_delivery.bowler_id = delivery_in.bowler_id
        last_delivery.batsman_id = delivery_in.batsman_id
        last_delivery.non_striker_id = delivery_in.non_striker_id
        last_delivery.runs = delivery_in.runs
        last_delivery.extra_type = delivery_in.extra_type
        last_delivery.extras = delivery_in.extras
        last_delivery.wicket_type = delivery_in.wicket_type
        last_delivery.player_out_id = delivery_in.player_out_id
        last_delivery.fielder_id = effective_fielder_id
        if delivery_in.commentary is not None:
            last_delivery.commentary = delivery_in.commentary

        await self._sync_match_state(aggregate, innings, match)

        await self.db.commit()
        await self.db.refresh(last_delivery)
        return last_delivery

    async def undo_last_delivery(
        self,
        match_id: int,
        innings_number: int,
    ) -> Delivery:
        """Deletes the most recent delivery and safely rolls back innings/match state using aggregate."""
        innings = await self.get_and_lock_innings(match_id, innings_number)
        match = innings.match_obj

        if match.status == MatchStatus.ABANDONED:
            raise_exception(400, "Cannot undo delivery for an abandoned match")

        deliv_res = await self.db.execute(
            select(Delivery)
            .where(Delivery.innings_id == innings.id)
            .order_by(Delivery.over, Delivery.ball)
        )
        all_deliveries = list(deliv_res.scalars().all())
        if not all_deliveries:
            raise_exception(404, "No deliveries found in this innings to undo")

        last_delivery = all_deliveries[-1]
        aggregate = hydrate_innings_aggregate(innings, match, all_deliveries)

        try:
            aggregate.undo_last_ball()
        except CricketDomainError as e:
            raise_exception(400, str(e))

        await self.db.delete(last_delivery)
        await self._sync_match_state(aggregate, innings, match)

        await self.db.commit()
        return last_delivery


# Dependency helper
def get_delivery_service(db: AsyncSession = Depends(get_db)) -> DeliveryService:
    return DeliveryService(db)


# Backward-compatible function wrappers
validate_delivery_payload = DeliveryRuleValidator.validate_payload
validate_playing_xis = DeliveryRuleValidator.validate_playing_xis

async def get_and_lock_innings(match_id: int, innings_number: int, db: AsyncSession) -> Innings:
    return await DeliveryService(db).get_and_lock_innings(match_id, innings_number)

async def record_delivery(match_id: int, innings_number: int, delivery_in: DeliveryCreate, db: AsyncSession):
    return await DeliveryService(db).record_delivery(match_id, innings_number, delivery_in)

async def update_last_delivery(match_id: int, innings_number: int, delivery_in: DeliveryCreate, db: AsyncSession):
    return await DeliveryService(db).update_last_delivery(match_id, innings_number, delivery_in)

async def undo_last_delivery(match_id: int, innings_number: int, db: AsyncSession):
    return await DeliveryService(db).undo_last_delivery(match_id, innings_number)

async def get_innings_deliveries(match_id: int, innings_number: int, db: AsyncSession) -> list[Delivery]:
    return await DeliveryService(db).get_innings_deliveries(match_id, innings_number)
