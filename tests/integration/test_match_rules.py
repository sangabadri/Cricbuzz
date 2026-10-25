import pytest
from httpx import AsyncClient
from tests.helpers import setup_scheduled_match_with_squads, create_player

pytestmark = pytest.mark.asyncio

async def test_consecutive_overs_prohibited(client: AsyncClient):
    setup = await setup_scheduled_match_with_squads(client)
    match_id = setup["match"]["id"]
    team_a = setup["team_a"]
    players_a = setup["players_a"]
    players_b = setup["players_b"]

    # Conduct toss
    await client.post(
        f"/api/v1/matches/{match_id}/toss",
        json={"toss_winner": team_a["id"], "toss_decision": "bat"},
    )

    striker = players_a[0]["id"]
    non_striker = players_a[1]["id"]
    bowler_1 = players_b[5]["id"]

    # Bowl complete over 0 with bowler_1 (6 legal balls)
    for ball in range(1, 7):
        resp = await client.post(
            f"/api/v1/matches/{match_id}/innings/1/deliveries",
            json={
                "over": 0, "ball": ball, "bowler_id": bowler_1,
                "batsman_id": striker, "non_striker_id": non_striker,
                "runs": 0, "extras": 0
            }
        )
        assert resp.status_code == 200, resp.text

    # Attempt to bowl over 1 with the same bowler_1 -> Should be rejected!
    resp_consecutive = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 1, "ball": 1, "bowler_id": bowler_1,
            "batsman_id": non_striker, "non_striker_id": striker,
            "runs": 0, "extras": 0
        }
    )
    assert resp_consecutive.status_code == 400
    assert "consecutive overs" in resp_consecutive.json()["detail"].lower()

async def test_bowler_without_bowling_style_cannot_bowl(client: AsyncClient):
    setup = await setup_scheduled_match_with_squads(client)
    match_id = setup["match"]["id"]
    team_a = setup["team_a"]
    players_a = setup["players_a"]
    players_b = setup["players_b"]

    await client.post(
        f"/api/v1/matches/{match_id}/toss",
        json={"toss_winner": team_a["id"], "toss_decision": "bat"},
    )

    striker = players_a[0]["id"]
    non_striker = players_a[1]["id"]
    # players_b[0] is a pure batsman with no bowling style
    pure_batsman_bowler = players_b[0]["id"]

    resp = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": pure_batsman_bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert resp.status_code == 400
    assert "bowling style" in resp.json()["detail"].lower()

async def test_non_squad_player_rejected(client: AsyncClient):
    setup = await setup_scheduled_match_with_squads(client)
    match_id = setup["match"]["id"]
    team_a = setup["team_a"]
    players_a = setup["players_a"]
    players_b = setup["players_b"]

    await client.post(
        f"/api/v1/matches/{match_id}/toss",
        json={"toss_winner": team_a["id"], "toss_decision": "bat"},
    )

    # Create an outside player not in the match squad
    outside_player = await create_player(client, "Rando Player", role="batsman")

    resp = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": players_b[5]["id"],
            "batsman_id": outside_player["id"], "non_striker_id": players_a[1]["id"],
            "runs": 0, "extras": 0
        }
    )
    assert resp.status_code == 400
    assert "not in batting team's playing xi" in resp.json()["detail"].lower()

async def test_caught_with_batting_team_fielder_rejected(client: AsyncClient):
    setup = await setup_scheduled_match_with_squads(client)
    match_id = setup["match"]["id"]
    team_a = setup["team_a"]
    players_a = setup["players_a"]
    players_b = setup["players_b"]

    await client.post(
        f"/api/v1/matches/{match_id}/toss",
        json={"toss_winner": team_a["id"], "toss_decision": "bat"},
    )

    striker = players_a[0]["id"]
    non_striker = players_a[1]["id"]
    bowler = players_b[5]["id"]
    # Batting teammate players_a[2] cannot be the fielder who caught the ball!
    invalid_fielder = players_a[2]["id"]

    resp = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "caught",
            "player_out_id": striker,
            "fielder_id": invalid_fielder
        }
    )
    assert resp.status_code == 400
    assert "not in bowling team's playing xi" in resp.json()["detail"].lower()

async def test_invalid_over_progression_rejected(client: AsyncClient):
    setup = await setup_scheduled_match_with_squads(client)
    match_id = setup["match"]["id"]
    team_a = setup["team_a"]
    players_a = setup["players_a"]
    players_b = setup["players_b"]

    await client.post(
        f"/api/v1/matches/{match_id}/toss",
        json={"toss_winner": team_a["id"], "toss_decision": "bat"},
    )

    striker = players_a[0]["id"]
    non_striker = players_a[1]["id"]
    bowler = players_b[5]["id"]

    # Ball 1
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert r1.status_code == 200

    # Skipping to Ball 3 (instead of ball 2) -> Should be rejected
    r_skip_ball = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 3, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert r_skip_ball.status_code == 400
    assert "expected ball 2" in r_skip_ball.json()["detail"].lower()

    # Skipping to Over 1 when over 0 is not complete -> Should be rejected
    r_skip_over = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 1, "ball": 1, "bowler_id": players_b[6]["id"],
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert r_skip_over.status_code == 400
    assert "still in progress" in r_skip_over.json()["detail"].lower()

async def test_match_abandonment_flow(client: AsyncClient):
    setup = await setup_scheduled_match_with_squads(client)
    match_id = setup["match"]["id"]
    team_a = setup["team_a"]
    team_b = setup["team_b"]
    players_a = setup["players_a"]
    players_b = setup["players_b"]

    await client.post(
        f"/api/v1/matches/{match_id}/toss",
        json={"toss_winner": team_a["id"], "toss_decision": "bat"},
    )

    # Bowl 1 delivery
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": players_b[5]["id"],
            "batsman_id": players_a[0]["id"], "non_striker_id": players_a[1]["id"],
            "runs": 1, "extras": 0
        }
    )
    assert r1.status_code == 200

    # Abandon match (e.g. rain stops play permanently)
    abandon_resp = await client.post(f"/api/v1/matches/{match_id}/abandon")
    assert abandon_resp.status_code == 200
    assert abandon_resp.json()["status"] == "abandoned"

    # Attempting any subsequent delivery should now fail
    r_after = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 2, "bowler_id": players_b[5]["id"],
            "batsman_id": players_a[1]["id"], "non_striker_id": players_a[0]["id"],
            "runs": 0, "extras": 0
        }
    )
    assert r_after.status_code == 400
    assert "abandoned" in r_after.json()["detail"].lower()

    # Team stats should record matches_abandoned = 1
    t1_stats = (await client.get(f"/api/v1/team/{team_a['id']}/stats")).json()
    t2_stats = (await client.get(f"/api/v1/team/{team_b['id']}/stats")).json()

    assert t1_stats["matches_played"] == 1
    assert t1_stats["matches_abandoned"] == 1
    assert t1_stats["matches_won"] == 0

    assert t2_stats["matches_played"] == 1
    assert t2_stats["matches_abandoned"] == 1
    assert t2_stats["matches_won"] == 0
