import pytest
from httpx import AsyncClient
from tests.helpers import setup_scheduled_match_with_squads

pytestmark = pytest.mark.asyncio

async def test_full_match_lifecycle_e2e(client: AsyncClient):
    # 1. Setup Match with Teams and Playing XIs
    setup = await setup_scheduled_match_with_squads(client)
    match_id = setup["match"]["id"]
    team_a = setup["team_a"]
    team_b = setup["team_b"]
    players_a = setup["players_a"]
    players_b = setup["players_b"]

    # 2. Conduct Toss: India elects to BAT
    toss_resp = await client.post(
        f"/api/v1/matches/{match_id}/toss",
        json={"toss_winner": team_a["id"], "toss_decision": "bat"},
    )
    assert toss_resp.status_code == 200, toss_resp.text
    assert toss_resp.json()["status"] == "toss_done"

    # 3. 1st Innings: India Batting, Australia Bowling
    striker = players_a[0]["id"]
    non_striker = players_a[1]["id"]
    bowler_1 = players_b[5]["id"]

    # Over 0: Bowled by bowler_1
    # Ball 1: dot
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert r1.status_code == 200, r1.text

    # Ball 2: 4 runs (boundary)
    r2 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 2, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 4, "extras": 0
        }
    )
    assert r2.status_code == 200, r2.text

    # Ball 3: 1 run (rotates strike to non_striker)
    r3 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 3, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 1, "extras": 0
        }
    )
    assert r3.status_code == 200, r3.text
    striker, non_striker = non_striker, striker

    # Ball 4: wide (1 extra, ball is re-bowled)
    r4 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 4, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extra_type": "wide", "extras": 1
        }
    )
    assert r4.status_code == 200, r4.text

    # Ball 5 (4th legal ball): 0 runs
    r5 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 5, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0
        }
    )
    assert r5.status_code == 200, r5.text

    # Ball 6 (5th legal ball): 6 runs (six)
    r6 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 6, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 6, "extras": 0
        }
    )
    assert r6.status_code == 200, r6.text

    # Ball 7 (6th legal ball): 1 run (single on last ball of over)
    r7 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 7, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 1, "extras": 0
        }
    )
    assert r7.status_code == 200, r7.text
    # Single rotates, then end-of-over rotates -> striker retains strike
    # striker is players_a[1]["id"], non_striker is players_a[0]["id"]
    assert striker == players_a[1]["id"]
    assert non_striker == players_a[0]["id"]

    # Over 1: Bowled by bowler_2 (players_b[6]["id"])
    bowler_2 = players_b[6]["id"]

    # Ball 1: Wicket! CAUGHT by fielder (players_b[7]["id"])
    w1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 1, "ball": 1, "bowler_id": bowler_2,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "caught",
            "player_out_id": striker,
            "fielder_id": players_b[7]["id"]
        }
    )
    assert w1.status_code == 200, w1.text

    # New batter walks in: players_a[2]["id"]
    striker = players_a[2]["id"]

    # Balls 2..6: 5 consecutive bowled wickets by bowler_2
    next_batters = [players_a[3]["id"], players_a[4]["id"], players_a[5]["id"], players_a[6]["id"], players_a[7]["id"]]
    for b_idx in range(2, 7):
        w_resp = await client.post(
            f"/api/v1/matches/{match_id}/innings/1/deliveries",
            json={
                "over": 1, "ball": b_idx, "bowler_id": bowler_2,
                "batsman_id": striker, "non_striker_id": non_striker,
                "runs": 0, "extras": 0,
                "wicket_type": "bowled",
                "player_out_id": striker,
            }
        )
        assert w_resp.status_code == 200, w_resp.text
        striker = next_batters[b_idx - 2]

    # Over 1 complete! Total wickets = 6. Over 1 was a maiden wicket-over!
    # Over 2: Bowled by bowler_1 (players_b[5]["id"])
    # End of over strike rotation: non_striker (players_a[0]["id"]) and striker swap:
    striker, non_striker = non_striker, striker

    remaining_batters = [players_a[8]["id"], players_a[9]["id"], players_a[10]["id"]]
    # Ball 1: Wicket 7 (bowled striker players_a[0]["id"])
    w7 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 2, "ball": 1, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "bowled",
            "player_out_id": striker,
        }
    )
    assert w7.status_code == 200, w7.text
    striker = remaining_batters[0]

    # Ball 2: Wicket 8
    w8 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 2, "ball": 2, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "bowled",
            "player_out_id": striker,
        }
    )
    assert w8.status_code == 200, w8.text
    striker = remaining_batters[1]

    # Ball 3: Wicket 9
    w9 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 2, "ball": 3, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "bowled",
            "player_out_id": striker,
        }
    )
    assert w9.status_code == 200, w9.text
    striker = remaining_batters[2]

    # Ball 4: Wicket 10 (ALL OUT!)
    w10 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 2, "ball": 4, "bowler_id": bowler_1,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "bowled",
            "player_out_id": striker,
        }
    )
    assert w10.status_code == 200, w10.text

    # Verify Innings 1 is completed and match is in INNINGS_BREAK
    match_after_inn1 = (await client.get(f"/api/v1/matches/{match_id}")).json()
    assert match_after_inn1["status"] == "innings_break"

    # 4. 2nd Innings: Australia chases target of 14 (13 + 1)
    aus_striker = players_b[0]["id"]
    aus_non_striker = players_b[1]["id"]
    ind_bowler = players_a[5]["id"]

    # Ball 1: 6 runs
    inn2_b1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/2/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": ind_bowler,
            "batsman_id": aus_striker, "non_striker_id": aus_non_striker,
            "runs": 6, "extras": 0
        }
    )
    assert inn2_b1.status_code == 200, inn2_b1.text

    # Ball 2: 4 runs
    inn2_b2 = await client.post(
        f"/api/v1/matches/{match_id}/innings/2/deliveries",
        json={
            "over": 0, "ball": 2, "bowler_id": ind_bowler,
            "batsman_id": aus_striker, "non_striker_id": aus_non_striker,
            "runs": 4, "extras": 0
        }
    )
    assert inn2_b2.status_code == 200, inn2_b2.text

    # Ball 3: 4 runs -> Target 14 reached!
    inn2_b3 = await client.post(
        f"/api/v1/matches/{match_id}/innings/2/deliveries",
        json={
            "over": 0, "ball": 3, "bowler_id": ind_bowler,
            "batsman_id": aus_striker, "non_striker_id": aus_non_striker,
            "runs": 4, "extras": 0
        }
    )
    assert inn2_b3.status_code == 200, inn2_b3.text

    # Verify Match is COMPLETED and Australia is winner
    match_final = (await client.get(f"/api/v1/matches/{match_id}")).json()
    assert match_final["status"] == "completed"
    assert match_final["winner"] == team_b["id"]

    # 5. Award Man of the Match to bowler_2 (who took 6 wickets!)
    mom_resp = await client.post(
        f"/api/v1/matches/{match_id}/mom",
        json={"player_id": bowler_2}
    )
    assert mom_resp.status_code == 200, mom_resp.text
    assert mom_resp.json()["mom"] == bowler_2

    # 6. Verify Full Scorecard
    sc_resp = await client.get(f"/api/v1/matches/{match_id}/scorecard")
    assert sc_resp.status_code == 200, sc_resp.text
    sc_data = sc_resp.json()
    assert sc_data["status"] == "completed"
    assert sc_data["mom_id"] == bowler_2
    assert sc_data["mom_name"] == players_b[6]["name"]
    assert len(sc_data["innings"]) == 2

    inn1_sc = sc_data["innings"][0]
    assert inn1_sc["runs"] == 13
    assert inn1_sc["wickets"] == 10
    assert len(inn1_sc["fall_of_wickets"]) == 10

    inn2_sc = sc_data["innings"][1]
    assert inn2_sc["runs"] == 14
    assert inn2_sc["wickets"] == 0
    assert inn2_sc["target"] == 14

    # 7. Verify Live State Endpoint
    live_resp = await client.get(f"/api/v1/matches/{match_id}/live")
    assert live_resp.status_code == 200, live_resp.text
    live_data = live_resp.json()
    assert live_data["match_id"] == match_id
    assert live_data["status"] == "completed"
    assert live_data["target"] == 14
    assert live_data["runs"] == 14

    # 8. Verify Career Stats for Star Performer (bowler_2)
    p_stats_resp = await client.get(f"/api/v1/players/{bowler_2}/stats")
    assert p_stats_resp.status_code == 200, p_stats_resp.text
    p_stats = p_stats_resp.json()
    assert p_stats["bowling"]["wickets"] == 6
    assert p_stats["bowling"]["maidens"] == 1
    assert p_stats["bowling"]["runs_conceded"] == 0

    # 9. Verify Team Stats
    aus_stats_resp = await client.get(f"/api/v1/team/{team_b['id']}/stats")
    assert aus_stats_resp.status_code == 200, aus_stats_resp.text
    aus_stats = aus_stats_resp.json()
    assert aus_stats["matches_played"] == 1
    assert aus_stats["matches_won"] == 1
    assert aus_stats["matches_lost"] == 0
    assert aus_stats["win_percentage"] == 100.0

    ind_stats_resp = await client.get(f"/api/v1/team/{team_a['id']}/stats")
    assert ind_stats_resp.status_code == 200, ind_stats_resp.text
    ind_stats = ind_stats_resp.json()
    assert ind_stats["matches_played"] == 1
    assert ind_stats["matches_won"] == 0
    assert ind_stats["matches_lost"] == 1
    assert ind_stats["win_percentage"] == 0.0
