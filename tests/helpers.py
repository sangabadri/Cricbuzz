from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from httpx import AsyncClient

IST = ZoneInfo("Asia/Kolkata")

async def create_team(client: AsyncClient, name: str) -> dict:
    resp = await client.post("/api/v1/team/", json={"name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()

async def create_player(
    client: AsyncClient,
    name: str,
    role: str = "batsman",
    batting: str = "right-handed batsman",
    bowling: str | None = None,
) -> dict:
    payload = {
        "name": name,
        "role": role,
        "batting": batting,
        "bowling": bowling,
    }
    resp = await client.post("/api/v1/players/", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()

async def create_test_teams_and_players(client: AsyncClient) -> dict:
    team_a = await create_team(client, "India")
    team_b = await create_team(client, "Australia")

    # 15 players for Team A:
    # 4 batsmen, 1 wicketkeeper, 3 allrounders, 7 bowlers
    players_a = []
    for i in range(1, 5):
        p = await create_player(client, f"IND Batter {i}", role="batsman")
        players_a.append(p)
    p_wk_a = await create_player(client, "IND Keeper 1", role="wicketkeeper")
    players_a.append(p_wk_a)
    for i in range(1, 4):
        p = await create_player(client, f"IND AllRounder {i}", role="all-rounder", bowling="right-arm fast")
        players_a.append(p)
    for i in range(1, 8):
        p = await create_player(client, f"IND Bowler {i}", role="bowler", bowling="right-arm fast")
        players_a.append(p)

    # 15 players for Team B:
    players_b = []
    for i in range(1, 5):
        p = await create_player(client, f"AUS Batter {i}", role="batsman")
        players_b.append(p)
    p_wk_b = await create_player(client, "AUS Keeper 1", role="wicketkeeper")
    players_b.append(p_wk_b)
    for i in range(1, 4):
        p = await create_player(client, f"AUS AllRounder {i}", role="all-rounder", bowling="right-arm fast")
        players_b.append(p)
    for i in range(1, 8):
        p = await create_player(client, f"AUS Bowler {i}", role="bowler", bowling="right-arm fast")
        players_b.append(p)

    return {
        "team_a": team_a,
        "team_b": team_b,
        "players_a": players_a,
        "players_b": players_b,
    }

async def setup_scheduled_match_with_squads(client: AsyncClient) -> dict:
    data = await create_test_teams_and_players(client)
    team_a = data["team_a"]
    team_b = data["team_b"]
    players_a = data["players_a"]
    players_b = data["players_b"]

    match_date = (datetime.now(IST) + timedelta(days=2)).isoformat()
    match_resp = await client.post(
        "/api/v1/matches/",
        json={
            "team_a": team_a["id"],
            "team_b": team_b["id"],
            "venue": "Wankhede Stadium, Mumbai",
            "match_date": match_date,
            "format": "t20",
        },
    )
    assert match_resp.status_code == 200, match_resp.text
    match_data = match_resp.json()

    # Submit squad for Team A: 11 playing XI, 4 bench
    # Players 0..10 playing XI, 11..14 bench
    squad_a_payload = {
        "team_id": team_a["id"],
        "captain_id": players_a[0]["id"],
        "wicket_keeper_id": players_a[4]["id"],
        "players": [
            {"player_id": p["id"], "is_playing_xi": idx < 11}
            for idx, p in enumerate(players_a)
        ],
    }
    resp_squad_a = await client.post(f"/api/v1/matches/{match_data['id']}/squad", json=squad_a_payload)
    assert resp_squad_a.status_code == 200, resp_squad_a.text

    # Submit squad for Team B: 11 playing XI, 4 bench
    squad_b_payload = {
        "team_id": team_b["id"],
        "captain_id": players_b[0]["id"],
        "wicket_keeper_id": players_b[4]["id"],
        "players": [
            {"player_id": p["id"], "is_playing_xi": idx < 11}
            for idx, p in enumerate(players_b)
        ],
    }
    resp_squad_b = await client.post(f"/api/v1/matches/{match_data['id']}/squad", json=squad_b_payload)
    assert resp_squad_b.status_code == 200, resp_squad_b.text

    return {
        "match": match_data,
        "team_a": team_a,
        "team_b": team_b,
        "players_a": players_a,
        "players_b": players_b,
    }
