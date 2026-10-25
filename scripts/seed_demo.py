import asyncio
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, delete

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "DB_HOST" not in os.environ:
    os.environ["DB_HOST"] = "localhost"

from app.config import settings
from app.models.base import Base
from app.models.team import Team
from app.models.player import Player
from app.models.match import Match
from app.models.squad import Squad, SquadPlayer
from app.models.innings import Innings
from app.models.delivery import Delivery
from app.schemas.enums import (
    MatchFormat,
    MatchStatus,
    InningsStatus,
    TossDecision,
    Role,
    BattingStyle,
    BowlingStyle,
    WicketType,
    ExtraType,
)

IST = ZoneInfo("Asia/Kolkata")
DATABASE_URL = (
    f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

IND_PLAYERS = [
    {"name": "Rohit Sharma", "role": Role.BATSMAN, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_SPIN},
    {"name": "Virat Kohli", "role": Role.BATSMAN, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_MEDIUM},
    {"name": "Rishabh Pant", "role": Role.WICKETKEEPER, "batting": BattingStyle.LEFT_HANDED, "bowling": None},
    {"name": "Suryakumar Yadav", "role": Role.BATSMAN, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_SPIN},
    {"name": "Hardik Pandya", "role": Role.ALLROUNDER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_FAST},
    {"name": "Shivam Dube", "role": Role.ALLROUNDER, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_MEDIUM},
    {"name": "Ravindra Jadeja", "role": Role.ALLROUNDER, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.LEFT_ARM_SPIN},
    {"name": "Axar Patel", "role": Role.ALLROUNDER, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.LEFT_ARM_SPIN},
    {"name": "Kuldeep Yadav", "role": Role.BOWLER, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.LEFT_ARM_SPIN},
    {"name": "Jasprit Bumrah", "role": Role.BOWLER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_FAST},
    {"name": "Arshdeep Singh", "role": Role.BOWLER, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.LEFT_ARM_FAST},
    # Bench
    {"name": "Yashasvi Jaiswal", "role": Role.BATSMAN, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_SPIN},
    {"name": "Sanju Samson", "role": Role.WICKETKEEPER, "batting": BattingStyle.RIGHT_HANDED, "bowling": None},
    {"name": "Mohammed Siraj", "role": Role.BOWLER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_FAST},
    {"name": "Yuzvendra Chahal", "role": Role.BOWLER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_SPIN},
]

AUS_PLAYERS = [
    {"name": "Travis Head", "role": Role.BATSMAN, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_SPIN},
    {"name": "David Warner", "role": Role.BATSMAN, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_MEDIUM},
    {"name": "Mitchell Marsh", "role": Role.ALLROUNDER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_MEDIUM},
    {"name": "Glenn Maxwell", "role": Role.ALLROUNDER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_SPIN},
    {"name": "Marcus Stoinis", "role": Role.ALLROUNDER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_MEDIUM},
    {"name": "Tim David", "role": Role.BATSMAN, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_SPIN},
    {"name": "Matthew Wade", "role": Role.WICKETKEEPER, "batting": BattingStyle.LEFT_HANDED, "bowling": None},
    {"name": "Pat Cummins", "role": Role.BOWLER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_FAST},
    {"name": "Mitchell Starc", "role": Role.BOWLER, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.LEFT_ARM_FAST},
    {"name": "Adam Zampa", "role": Role.BOWLER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_SPIN},
    {"name": "Josh Hazlewood", "role": Role.BOWLER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_FAST},
    # Bench
    {"name": "Josh Inglis", "role": Role.WICKETKEEPER, "batting": BattingStyle.RIGHT_HANDED, "bowling": None},
    {"name": "Ashton Agar", "role": Role.ALLROUNDER, "batting": BattingStyle.LEFT_HANDED, "bowling": BowlingStyle.LEFT_ARM_SPIN},
    {"name": "Nathan Ellis", "role": Role.BOWLER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_FAST},
    {"name": "Cameron Green", "role": Role.ALLROUNDER, "batting": BattingStyle.RIGHT_HANDED, "bowling": BowlingStyle.RIGHT_ARM_FAST},
]

async def seed_data():
    print(f"Connecting to database: {DATABASE_URL}")

    # Ensure PostgreSQL enum types have any updated enum values
    import psycopg
    raw_url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    try:
        with psycopg.connect(raw_url, autocommit=True) as pg_conn:
            for val in ("RIGHT_ARM_SPIN", "LEFT_ARM_SPIN"):
                try:
                    pg_conn.execute(f"ALTER TYPE bowlingstyle ADD VALUE IF NOT EXISTS '{val}'")
                except Exception:
                    pass
    except Exception as e:
        print(f"Enum check warning: {e}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # 1. Teams
        async def get_or_create_team(name: str) -> Team:
            res = await db.execute(select(Team).where(Team.name == name))
            team = res.scalar_one_or_none()
            if not team:
                team = Team(name=name)
                db.add(team)
                await db.flush()
            return team

        team_ind = await get_or_create_team("India")
        team_aus = await get_or_create_team("Australia")

        # 2. Players
        async def get_or_create_players(player_list: list[dict], team_id: int) -> list[Player]:
            db_players = []
            for p in player_list:
                res = await db.execute(select(Player).where(Player.name == p["name"]))
                player = res.scalar_one_or_none()
                if not player:
                    player = Player(
                        name=p["name"],
                        role=p["role"],
                        batting=p["batting"],
                        bowling=p["bowling"],
                    )
                    db.add(player)
                    await db.flush()
                db_players.append(player)
            return db_players

        ind_p = await get_or_create_players(IND_PLAYERS, team_ind.id)
        aus_p = await get_or_create_players(AUS_PLAYERS, team_aus.id)

        print(f"Created/Found {len(ind_p)} India players and {len(aus_p)} Australia players")

        # 3. Match 1: Completed Historic Thriller (ICC T20 World Cup 2024 - Super 8)
        res_m1 = await db.execute(select(Match).where(Match.venue == "Daren Sammy Cricket Ground, St Lucia"))
        m1 = res_m1.scalar_one_or_none()

        if not m1:
            m1 = Match(
                team_a=team_ind.id,
                team_b=team_aus.id,
                venue="Daren Sammy Cricket Ground, St Lucia",
                match_date=datetime(2024, 6, 24, 20, 0, tzinfo=IST),
                format=MatchFormat.T20,
                status=MatchStatus.COMPLETED,
                toss_winner=team_aus.id,
                toss_decision=TossDecision.BOWL,
                winner=team_ind.id,
                mom=ind_p[0].id,  # Rohit Sharma
            )
            db.add(m1)
            await db.flush()

            # Squads for Match 1
            squad_ind = Squad(
                match_id=m1.id,
                team_id=team_ind.id,
                captain_id=ind_p[0].id,
                wicket_keeper_id=ind_p[2].id,
            )
            db.add(squad_ind)
            await db.flush()
            for idx, p in enumerate(ind_p):
                db.add(SquadPlayer(squad_id=squad_ind.id, player_id=p.id, is_playing_xi=idx < 11))

            squad_aus = Squad(
                match_id=m1.id,
                team_id=team_aus.id,
                captain_id=aus_p[2].id,
                wicket_keeper_id=aus_p[6].id,
            )
            db.add(squad_aus)
            await db.flush()
            for idx, p in enumerate(aus_p):
                db.add(SquadPlayer(squad_id=squad_aus.id, player_id=p.id, is_playing_xi=idx < 11))

            # Innings 1 (India: 205/5 in 20.0 overs)
            inn1 = Innings(
                match_id=m1.id,
                innings_number=1,
                batting_team_id=team_ind.id,
                bowling_team_id=team_aus.id,
                status=InningsStatus.COMPLETED,
            )
            db.add(inn1)
            await db.flush()

            # Simulate 20 overs for Innings 1:
            # 5 bowlers rotating: Starc(8), Hazlewood(10), Cummins(7), Zampa(9), Stoinis(4)
            aus_bowlers = [aus_p[8], aus_p[10], aus_p[7], aus_p[9], aus_p[4]]
            striker_idx = 0  # Rohit Sharma
            non_striker_idx = 1  # Virat Kohli
            wickets_fallen = 0
            runs_pattern = [0, 4, 1, 6, 0, 1]  # ~12 runs an over

            for ov in range(20):
                bowler = aus_bowlers[ov % len(aus_bowlers)]
                # Ensure no consecutive bowler
                if ov > 0 and bowler.id == aus_bowlers[(ov - 1) % len(aus_bowlers)].id:
                    bowler = aus_bowlers[(ov + 1) % len(aus_bowlers)]

                for ball in range(1, 7):
                    # Introduce occasional wickets
                    w_type = None
                    p_out = None
                    f_id = None
                    runs = runs_pattern[(ball + ov) % len(runs_pattern)]

                    if (ov == 1 and ball == 4 and wickets_fallen == 0):
                        # Kohli out
                        w_type = WicketType.CAUGHT
                        p_out = ind_p[non_striker_idx].id
                        f_id = aus_p[0].id
                        runs = 0
                        wickets_fallen += 1
                        non_striker_idx = 2  # Pant in
                    elif (ov == 11 and ball == 2 and wickets_fallen == 1):
                        # Rohit Sharma out for 92!
                        w_type = WicketType.BOWLED
                        p_out = ind_p[striker_idx].id
                        runs = 0
                        wickets_fallen += 1
                        striker_idx = 3  # Suryakumar in
                    elif (ov == 14 and ball == 5 and wickets_fallen == 2):
                        w_type = WicketType.CAUGHT
                        p_out = ind_p[non_striker_idx].id
                        f_id = aus_p[6].id
                        runs = 0
                        wickets_fallen += 1
                        non_striker_idx = 4  # Hardik Pandya in
                    elif (ov == 18 and ball == 3 and wickets_fallen == 3):
                        w_type = WicketType.BOWLED
                        p_out = ind_p[striker_idx].id
                        runs = 0
                        wickets_fallen += 1
                        striker_idx = 5  # Shivam Dube in

                    db.add(Delivery(
                        innings_id=inn1.id,
                        over=ov,
                        ball=ball,
                        bowler_id=bowler.id,
                        batsman_id=ind_p[striker_idx].id,
                        non_striker_id=ind_p[non_striker_idx].id,
                        runs=runs,
                        extra_type=None,
                        extras=0,
                        wicket_type=w_type,
                        player_out_id=p_out,
                        fielder_id=f_id,
                    ))

                    # Rotate strike
                    if runs % 2 != 0:
                        striker_idx, non_striker_idx = non_striker_idx, striker_idx

                # End of over strike rotation
                striker_idx, non_striker_idx = non_striker_idx, striker_idx

            # Innings 2 (Australia: 181/7 in 20.0 overs)
            inn2 = Innings(
                match_id=m1.id,
                innings_number=2,
                batting_team_id=team_aus.id,
                bowling_team_id=team_ind.id,
                status=InningsStatus.COMPLETED,
                target=206,
            )
            db.add(inn2)
            await db.flush()

            # 5 Indian bowlers: Arshdeep(10), Bumrah(9), Axar(7), Kuldeep(8), Hardik(4)
            ind_bowlers = [ind_p[10], ind_p[9], ind_p[7], ind_p[8], ind_p[4]]
            striker_idx = 0  # Travis Head
            non_striker_idx = 1  # David Warner
            wickets_fallen = 0
            runs_pattern_2 = [1, 0, 4, 1, 2, 0]

            for ov in range(20):
                bowler = ind_bowlers[ov % len(ind_bowlers)]
                for ball in range(1, 7):
                    w_type = None
                    p_out = None
                    f_id = None
                    runs = runs_pattern_2[(ball + ov) % len(runs_pattern_2)]

                    if ov == 0 and ball == 6 and wickets_fallen == 0:
                        # Warner out
                        w_type = WicketType.CAUGHT
                        p_out = aus_p[non_striker_idx].id
                        f_id = ind_p[3].id
                        runs = 0
                        wickets_fallen += 1
                        non_striker_idx = 2  # Marsh in
                    elif ov == 8 and ball == 4 and wickets_fallen == 1:
                        # Marsh out
                        w_type = WicketType.CAUGHT
                        p_out = aus_p[non_striker_idx].id
                        f_id = ind_p[7].id  # Axar stunner
                        runs = 0
                        wickets_fallen += 1
                        non_striker_idx = 3  # Maxwell in
                    elif ov == 16 and ball == 3 and wickets_fallen == 2:
                        # Head out to Bumrah
                        w_type = WicketType.BOWLED
                        p_out = aus_p[striker_idx].id
                        runs = 0
                        wickets_fallen += 1
                        striker_idx = 4  # Stoinis in

                    db.add(Delivery(
                        innings_id=inn2.id,
                        over=ov,
                        ball=ball,
                        bowler_id=bowler.id,
                        batsman_id=aus_p[striker_idx].id,
                        non_striker_id=aus_p[non_striker_idx].id,
                        runs=runs,
                        extra_type=None,
                        extras=0,
                        wicket_type=w_type,
                        player_out_id=p_out,
                        fielder_id=f_id,
                    ))

                    if runs % 2 != 0:
                        striker_idx, non_striker_idx = non_striker_idx, striker_idx

                striker_idx, non_striker_idx = non_striker_idx, striker_idx

            print("Seeded Match 1 (Completed 20-Over Blockbuster: IND vs AUS)")

        # 4. Match 2: LIVE In-Progress Match
        res_m2 = await db.execute(select(Match).where(Match.venue == "Melbourne Cricket Ground, Melbourne"))
        m2 = res_m2.scalar_one_or_none()

        if not m2:
            m2 = Match(
                team_a=team_ind.id,
                team_b=team_aus.id,
                venue="Melbourne Cricket Ground, Melbourne",
                match_date=datetime.now(IST),
                format=MatchFormat.T20,
                status=MatchStatus.LIVE,
                toss_winner=team_ind.id,
                toss_decision=TossDecision.BAT,
                winner=None,
            )
            db.add(m2)
            await db.flush()

            # Squads
            squad2_ind = Squad(
                match_id=m2.id,
                team_id=team_ind.id,
                captain_id=ind_p[0].id,
                wicket_keeper_id=ind_p[2].id,
            )
            db.add(squad2_ind)
            await db.flush()
            for idx, p in enumerate(ind_p):
                db.add(SquadPlayer(squad_id=squad2_ind.id, player_id=p.id, is_playing_xi=idx < 11))

            squad2_aus = Squad(
                match_id=m2.id,
                team_id=team_aus.id,
                captain_id=aus_p[2].id,
                wicket_keeper_id=aus_p[6].id,
            )
            db.add(squad2_aus)
            await db.flush()
            for idx, p in enumerate(aus_p):
                db.add(SquadPlayer(squad_id=squad2_aus.id, player_id=p.id, is_playing_xi=idx < 11))

            # Innings 1 (India completed: 186/5 in 20.0 overs)
            inn2_1 = Innings(
                match_id=m2.id,
                innings_number=1,
                batting_team_id=team_ind.id,
                bowling_team_id=team_aus.id,
                status=InningsStatus.COMPLETED,
            )
            db.add(inn2_1)
            await db.flush()

            # 20 overs for India in Innings 1
            aus_bowlers = [aus_p[8], aus_p[10], aus_p[7], aus_p[9], aus_p[4]]
            striker_idx = 0
            non_striker_idx = 1
            for ov in range(20):
                bowler = aus_bowlers[ov % len(aus_bowlers)]
                for ball in range(1, 7):
                    runs = 1 if ball % 2 == 1 else 2
                    db.add(Delivery(
                        innings_id=inn2_1.id,
                        over=ov,
                        ball=ball,
                        bowler_id=bowler.id,
                        batsman_id=ind_p[striker_idx].id,
                        non_striker_id=ind_p[non_striker_idx].id,
                        runs=runs,
                        extras=0,
                    ))
                    if runs % 2 != 0:
                        striker_idx, non_striker_idx = non_striker_idx, striker_idx
                striker_idx, non_striker_idx = non_striker_idx, striker_idx

            # Innings 2 (Australia: LIVE at 14.3 overs, 128/3, chasing 187)
            inn2_2 = Innings(
                match_id=m2.id,
                innings_number=2,
                batting_team_id=team_aus.id,
                bowling_team_id=team_ind.id,
                status=InningsStatus.IN_PROGRESS,
                target=187,
            )
            db.add(inn2_2)
            await db.flush()

            ind_bowlers = [ind_p[10], ind_p[9], ind_p[7], ind_p[8], ind_p[4]]
            striker_idx = 3  # Glenn Maxwell
            non_striker_idx = 4  # Marcus Stoinis

            # 14 completed overs
            for ov in range(14):
                bowler = ind_bowlers[ov % len(ind_bowlers)]
                for ball in range(1, 7):
                    runs = 1 if ball % 3 == 0 else 0
                    if ball == 4:
                        runs = 4
                    db.add(Delivery(
                        innings_id=inn2_2.id,
                        over=ov,
                        ball=ball,
                        bowler_id=bowler.id,
                        batsman_id=aus_p[striker_idx].id,
                        non_striker_id=aus_p[non_striker_idx].id,
                        runs=runs,
                        extras=0,
                    ))
                    if runs % 2 != 0:
                        striker_idx, non_striker_idx = non_striker_idx, striker_idx
                striker_idx, non_striker_idx = non_striker_idx, striker_idx

            # Over 14 (3 balls bowled so far): Jasprit Bumrah bowling to Glenn Maxwell!
            bumrah = ind_p[9]
            # Ball 1: dot
            db.add(Delivery(
                innings_id=inn2_2.id, over=14, ball=1,
                bowler_id=bumrah.id, batsman_id=aus_p[striker_idx].id,
                non_striker_id=aus_p[non_striker_idx].id, runs=0, extras=0
            ))
            # Ball 2: 1 run (rotates strike to Stoinis)
            db.add(Delivery(
                innings_id=inn2_2.id, over=14, ball=2,
                bowler_id=bumrah.id, batsman_id=aus_p[striker_idx].id,
                non_striker_id=aus_p[non_striker_idx].id, runs=1, extras=0
            ))
            striker_idx, non_striker_idx = non_striker_idx, striker_idx
            # Ball 3: 4 runs (boundary by Stoinis!)
            db.add(Delivery(
                innings_id=inn2_2.id, over=14, ball=3,
                bowler_id=bumrah.id, batsman_id=aus_p[striker_idx].id,
                non_striker_id=aus_p[non_striker_idx].id, runs=4, extras=0
            ))

            print("Seeded Match 2 (LIVE In-Progress Match: AUS chasing IND at MCG)")

        await db.commit()
        print("Data seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
