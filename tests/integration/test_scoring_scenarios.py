import pytest
from httpx import AsyncClient
from tests.helpers import setup_scheduled_match_with_squads

pytestmark = pytest.mark.asyncio

async def test_delivery_mistake_correction_flow(client: AsyncClient):
    """
    Tests PUT /matches/{id}/innings/{n}/deliveries/last to verify that
    correcting a delivery updates runs, bowler figures, dismissals, and FOW.
    """
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

    # Ball 1: Scorer accidentally records 4 runs instead of 1
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 4, "extras": 0
        }
    )
    assert r1.status_code == 200

    # Verify initial incorrect score (4/0)
    sc1 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc1["runs"] == 4
    b_stat1 = next(b for b in sc1["batting"] if b["player_id"] == striker)
    assert b_stat1["runs"] == 4
    assert b_stat1["fours"] == 1

    # Scorer corrects Ball 1 to 1 run via PUT /deliveries/last
    r_edit = await client.put(
        f"/api/v1/matches/{match_id}/innings/1/deliveries/last",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 1, "extras": 0
        }
    )
    assert r_edit.status_code == 200
    assert r_edit.json()["runs"] == 1

    # Verify scorecard immediately reflects the correction (1/0)
    sc2 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc2["runs"] == 1
    b_stat2 = next(b for b in sc2["batting"] if b["player_id"] == striker)
    assert b_stat2["runs"] == 1
    assert b_stat2["fours"] == 0

    bowler_stat2 = next(b for b in sc2["bowling"] if b["player_id"] == bowler)
    assert bowler_stat2["runs"] == 1

    # Ball 2: Scorer accidentally records a bowled dismissal
    r2 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 2, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "bowled",
            "player_out_id": striker
        }
    )
    assert r2.status_code == 200

    sc3 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc3["wickets"] == 1
    assert len(sc3["fall_of_wickets"]) == 1

    # Scorer corrects Ball 2: Wicket was overturned / mistaken entry -> change to dot ball!
    r_edit_w = await client.put(
        f"/api/v1/matches/{match_id}/innings/1/deliveries/last",
        json={
            "over": 0, "ball": 2, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": None,
            "player_out_id": None
        }
    )
    assert r_edit_w.status_code == 200
    assert r_edit_w.json()["wicket_type"] is None

    # Verify wickets is back to 0 and FOW is empty
    sc4 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc4["wickets"] == 0
    assert len(sc4["fall_of_wickets"]) == 0
    b_stat4 = next(b for b in sc4["batting"] if b["player_id"] == striker)
    assert not b_stat4["is_out"]
    bowler_stat4 = next(b for b in sc4["bowling"] if b["player_id"] == bowler)
    assert bowler_stat4["wickets"] == 0

async def test_non_striker_run_out_and_complex_extras(client: AsyncClient):
    """
    Tests:
    1. Compound extras: No-ball + 4 runs off bat (5 team runs, 4 to batter, 1 to extras).
    2. Byes: 2 byes (not charged to bowler's figures).
    3. Non-striker run out: Non-striker is dismissed while striker remains at crease,
       bowler is not credited with wicket.
    """
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
    fielder = players_b[6]["id"]

    # 1. No-ball + 4 runs off the bat
    # Extras = 1, Runs = 4 -> Total 5 runs. Does NOT count as a legal ball.
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 4, "extra_type": "noball", "extras": 1
        }
    )
    assert r1.status_code == 200, r1.text

    sc1 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc1["runs"] == 5
    assert sc1["extras"]["no_balls"] == 1
    assert sc1["extras"]["total"] == 1
    # 0 legal balls bowled so far
    assert sc1["overs"] == {"completed_overs": 0, "balls": 0, "total_legal_balls": 0}

    b_striker1 = next(b for b in sc1["batting"] if b["player_id"] == striker)
    assert b_striker1["runs"] == 4
    assert b_striker1["balls"] == 1
    assert b_striker1["fours"] == 1

    bowler1 = next(b for b in sc1["bowling"] if b["player_id"] == bowler)
    # Bowler conceded 4 off bat + 1 noball extra = 5
    assert bowler1["runs"] == 5
    assert bowler1["no_balls"] == 1

    # 2. 2 Byes (Legal ball 1)
    # Byes are added to team total and extras, but NOT credited to batsman or charged to bowler
    r2 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 2, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extra_type": "bye", "extras": 2
        }
    )
    assert r2.status_code == 200, r2.text

    sc2 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc2["runs"] == 7  # 5 + 2
    assert sc2["extras"]["byes"] == 2
    assert sc2["extras"]["total"] == 3
    assert sc2["overs"] == {"completed_overs": 0, "balls": 1, "total_legal_balls": 1}  # 1 legal ball

    bowler2 = next(b for b in sc2["bowling"] if b["player_id"] == bowler)
    # Bowler runs should STILL be 5 (byes do not count against bowler)
    assert bowler2["runs"] == 5

    # 3. Non-Striker Run Out (Legal ball 2)
    # Striker hits for 1 run, but non-striker is run out by fielder!
    r3 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 3, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 1, "extras": 0,
            "wicket_type": "run_out",
            "player_out_id": non_striker,
            "fielder_id": fielder
        }
    )
    assert r3.status_code == 200, r3.text

    sc3 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc3["runs"] == 8  # 7 + 1
    assert sc3["wickets"] == 1
    assert sc3["overs"] == {"completed_overs": 0, "balls": 2, "total_legal_balls": 2}

    # Striker should NOT be out
    b_striker = next(b for b in sc3["batting"] if b["player_id"] == striker)
    assert not b_striker["is_out"]
    assert b_striker["runs"] == 5  # 4 + 1

    # Non-striker MUST BE OUT
    b_non_striker = next(b for b in sc3["batting"] if b["player_id"] == non_striker)
    assert b_non_striker["is_out"]
    assert b_non_striker["dismissal"] is not None
    assert b_non_striker["dismissal"]["wicket_type"] == "run_out"
    assert b_non_striker["dismissal"]["fielder_id"] == fielder

    # Fall of Wickets verification
    assert len(sc3["fall_of_wickets"]) == 1
    fow = sc3["fall_of_wickets"][0]
    assert fow["wicket_number"] == 1
    assert fow["player_id"] == non_striker
    assert fow["score"] == 8

    # Bowler does not get credited with a run-out wicket
    bowler3 = next(b for b in sc3["bowling"] if b["player_id"] == bowler)
    assert bowler3["wickets"] == 0
    assert bowler3["runs"] == 6  # 5 from before + 1 run from bat


async def test_undo_last_delivery_flow(client: AsyncClient):
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

    # Ball 1: 4 runs
    r1 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 1, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 4, "extras": 0
        }
    )
    assert r1.status_code == 200

    # Ball 2: Bowled dismissal
    r2 = await client.post(
        f"/api/v1/matches/{match_id}/innings/1/deliveries",
        json={
            "over": 0, "ball": 2, "bowler_id": bowler,
            "batsman_id": striker, "non_striker_id": non_striker,
            "runs": 0, "extras": 0,
            "wicket_type": "bowled",
            "player_out_id": striker
        }
    )
    assert r2.status_code == 200

    sc = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc["runs"] == 4
    assert sc["wickets"] == 1
    assert sc["overs"] == {"completed_overs": 0, "balls": 2, "total_legal_balls": 2}

    # UNDO Ball 2 (delete wicket ball)
    del_resp = await client.delete(f"/api/v1/matches/{match_id}/innings/1/deliveries/last")
    assert del_resp.status_code == 200
    assert del_resp.json()["wicket_type"] == "bowled"

    # Verify score rolled back to 4/0, 0.1 overs
    sc_after_undo1 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc_after_undo1["runs"] == 4
    assert sc_after_undo1["wickets"] == 0
    assert sc_after_undo1["overs"] == {"completed_overs": 0, "balls": 1, "total_legal_balls": 1}

    # UNDO Ball 1 (delete 4-run ball)
    del_resp2 = await client.delete(f"/api/v1/matches/{match_id}/innings/1/deliveries/last")
    assert del_resp2.status_code == 200
    assert del_resp2.json()["runs"] == 4

    # Verify match reverted back to TOSS_DONE
    match_resp = await client.get(f"/api/v1/matches/{match_id}")
    assert match_resp.json()["status"] == "toss_done"

    sc_after_undo2 = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()["innings"][0]
    assert sc_after_undo2["runs"] == 0
    assert sc_after_undo2["overs"] == {"completed_overs": 0, "balls": 0, "total_legal_balls": 0}

    # Attempting to undo when no balls remain -> 404
    del_resp3 = await client.delete(f"/api/v1/matches/{match_id}/innings/1/deliveries/last")
    assert del_resp3.status_code == 404
    assert "no deliveries found" in del_resp3.json()["detail"].lower()

