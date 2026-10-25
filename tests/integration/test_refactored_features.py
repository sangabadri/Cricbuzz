import pytest
from httpx import AsyncClient
from tests.helpers import setup_scheduled_match_with_squads

pytestmark = pytest.mark.asyncio

async def test_delivery_idempotency_and_conflict(client: AsyncClient):
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

    payload = {
        "over": 0,
        "ball": 1,
        "bowler_id": bowler,
        "batsman_id": striker,
        "non_striker_id": non_striker,
        "runs": 4,
        "extras": 0,
        "commentary": "Edged and through the slips for four!",
    }

    # First submission -> 200 Created/OK
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json=payload,
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["runs"] == 4
    assert d1["commentary"] == "Edged and through the slips for four!"

    # Second submission for same ball without idempotency key -> rejected with 400
    r2 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json=payload,
    )
    assert r2.status_code == 400
    assert "expected ball 2" in r2.json()["detail"].lower()


async def test_toss_idempotency(client: AsyncClient):
    setup = await setup_scheduled_match_with_squads(client)
    match_id = setup["match"]["id"]
    team_a = setup["team_a"]
    team_b = setup["team_b"]

    toss_payload = {"toss_winner": team_a["id"], "toss_decision": "bat"}

    # 1. First toss
    r1 = await client.post(f"/api/v1/matches/{match_id}/toss", json=toss_payload)
    assert r1.status_code == 200
    assert r1.json()["status"] == "toss_done"

    # 2. Re-conducting the exact same toss -> Idempotent 200 OK
    r2 = await client.post(f"/api/v1/matches/{match_id}/toss", json=toss_payload)
    assert r2.status_code == 200
    assert r2.json()["status"] == "toss_done"

    # 3. Trying to change the toss -> 400 Bad Request
    r3 = await client.post(
        f"/api/v1/matches/{match_id}/toss",
        json={"toss_winner": team_b["id"], "toss_decision": "bowl"},
    )
    assert r3.status_code == 400
    assert "already been conducted" in r3.json()["detail"].lower()


async def test_batter_integrity_and_dismissed_player_cannot_bat(client: AsyncClient):
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

    # Ball 1: dot ball
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert r1.status_code == 200

    # Ball 2: Attempting to substitute batsman without a wicket -> 400
    unauthorized_batter = players_a[2]["id"]
    r2_invalid = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 2, "bowler_id": bowler,
            "batsman_id": unauthorized_batter, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert r2_invalid.status_code == 400
    assert "batters at crease must remain" in r2_invalid.json()["detail"].lower()

    # Ball 2: Valid delivery with a wicket (striker bowled)
    r2 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 2, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "bowled",
            "player_out_id": striker,
        }
    )
    assert r2.status_code == 200

    # Ball 3: Attempting to bring back the dismissed player (striker) -> 400
    r3_dismissed = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 3, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert r3_dismissed.status_code == 400
    assert "has already been dismissed in this innings" in r3_dismissed.json()["detail"].lower()


async def test_historical_edit_locks(client: AsyncClient):
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

    # Bowl 1 delivery
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 1, "extras": 0
        }
    )
    assert r1.status_code == 200

    # Abandon the match
    r_ab = await client.post(f"/api/v1/matches/{match_id}/abandon")
    assert r_ab.status_code == 200
    assert r_ab.json()["status"] == "abandoned"

    # Attempting to edit delivery on abandoned match -> 400
    r_edit = await client.put(
        f"/api/v1/matches/{match_id}/innings/1/deliveries/last",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 4, "extras": 0
        }
    )
    assert r_edit.status_code == 400
    assert "cannot modify delivery for match with status 'abandoned'" in r_edit.json()["detail"].lower()


async def test_match_search_functionality(client: AsyncClient):
    # Setup match which creates teams like "India" and "Australia"
    setup = await setup_scheduled_match_with_squads(client)
    team_a_name = setup["team_a"]["name"]

    # Search by partial team name
    resp = await client.get(f"/api/v1/matches/?search={team_a_name[:4]}")
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) >= 1
    assert any(m["id"] == setup["match"]["id"] for m in matches)
    assert matches[0]["team_a_name"] is not None
    assert matches[0]["team_b_name"] is not None


async def test_unplayed_career_stats_are_none(client: AsyncClient):
    # Create a fresh player who hasn't played any matches yet
    p_resp = await client.post(
        "/api/v1/players/",
        json={
            "name": "Rookie Debutant",
            "role": "batsman",
            "batting": "right-handed batsman",
            "bowling": None,
        }
    )
    assert p_resp.status_code == 200
    player_id = p_resp.json()["id"]

    stats_resp = await client.get(f"/api/v1/players/{player_id}/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()

    batting = stats["batting"]
    assert batting["innings"] == 0
    assert batting["runs"] == 0
    assert batting["average"] is None
    assert batting["strike_rate"] is None
    assert batting["highest_score"] is None

    bowling = stats["bowling"]
    assert bowling["innings"] == 0
    assert bowling["wickets"] == 0
    assert bowling["average"] is None
    assert bowling["economy"] is None
    assert bowling["best_bowling"] is None
