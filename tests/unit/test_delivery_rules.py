import pytest
from fastapi import HTTPException
from app.schemas.delivery import DeliveryCreate
from app.schemas.enums import ExtraType, WicketType
from app.services.delivery import validate_delivery_payload

def test_valid_delivery_payload():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=1,
        batsman_id=2,
        non_striker_id=3,
        runs=1,
        extra_type=None,
        extras=0,
        wicket_type=None,
        player_out_id=None,
        fielder_id=None,
    )
    # Should not raise
    validate_delivery_payload(d)

def test_invalid_runs():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=1,
        batsman_id=2,
        non_striker_id=3,
        runs=7,
        extra_type=None,
        extras=0,
    )
    with pytest.raises(HTTPException) as exc:
        validate_delivery_payload(d)
    assert exc.value.status_code == 400
    assert "Runs must be between 0 and 6" in exc.value.detail

def test_same_striker_and_non_striker():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=1,
        batsman_id=2,
        non_striker_id=2,
        runs=0,
    )
    with pytest.raises(HTTPException) as exc:
        validate_delivery_payload(d)
    assert exc.value.status_code == 400
    assert "Striker and non-striker cannot be the same" in exc.value.detail

def test_same_batsman_and_bowler():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=2,
        batsman_id=2,
        non_striker_id=3,
        runs=0,
    )
    with pytest.raises(HTTPException) as exc:
        validate_delivery_payload(d)
    assert exc.value.status_code == 400
    assert "Batsman and bowler cannot be the same" in exc.value.detail

def test_wide_without_extras():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=1,
        batsman_id=2,
        non_striker_id=3,
        runs=0,
        extra_type=ExtraType.WIDE,
        extras=0,
    )
    with pytest.raises(HTTPException) as exc:
        validate_delivery_payload(d)
    assert exc.value.status_code == 400
    assert "Extras must be at least 1" in exc.value.detail

def test_extras_without_extra_type():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=1,
        batsman_id=2,
        non_striker_id=3,
        runs=0,
        extra_type=None,
        extras=2,
    )
    with pytest.raises(HTTPException) as exc:
        validate_delivery_payload(d)
    assert exc.value.status_code == 400
    assert "Extras must be 0 when extra_type is None" in exc.value.detail

def test_caught_requires_fielder():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=1,
        batsman_id=2,
        non_striker_id=3,
        runs=0,
        wicket_type=WicketType.CAUGHT,
        player_out_id=2,
        fielder_id=None,
    )
    with pytest.raises(HTTPException) as exc:
        validate_delivery_payload(d)
    assert exc.value.status_code == 400
    assert "fielder_id is required" in exc.value.detail

def test_caught_fielder_cannot_be_bowler():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=1,
        batsman_id=2,
        non_striker_id=3,
        runs=0,
        wicket_type=WicketType.CAUGHT,
        player_out_id=2,
        fielder_id=1,  # same as bowler
    )
    with pytest.raises(HTTPException) as exc:
        validate_delivery_payload(d)
    assert exc.value.status_code == 400
    assert "fielder_id cannot be the bowler" in exc.value.detail

def test_bowled_cannot_have_fielder():
    d = DeliveryCreate(
        over=0,
        ball=1,
        bowler_id=1,
        batsman_id=2,
        non_striker_id=3,
        runs=0,
        wicket_type=WicketType.BOWLED,
        player_out_id=2,
        fielder_id=4,
    )
    with pytest.raises(HTTPException) as exc:
        validate_delivery_payload(d)
    assert exc.value.status_code == 400
    assert "fielder_id must be None" in exc.value.detail

def test_strike_rotation_logic():
    # Helper simulating strike rotation
    def rotate_strike(striker: int, non_striker: int, runs: int, is_last_ball_of_over: bool):
        s, ns = striker, non_striker
        if runs % 2 != 0:
            s, ns = ns, s
        if is_last_ball_of_over:
            s, ns = ns, s
        return s, ns

    # Single in middle of over rotates strike
    assert rotate_strike(10, 20, 1, False) == (20, 10)
    # Dot ball keeps strike
    assert rotate_strike(10, 20, 0, False) == (10, 20)
    # Boundary (4) keeps strike
    assert rotate_strike(10, 20, 4, False) == (10, 20)
    # 2 runs keeps strike
    assert rotate_strike(10, 20, 2, False) == (10, 20)
    # Single on last ball rotates once for run, once for over change -> retains strike!
    assert rotate_strike(10, 20, 1, True) == (10, 20)
    # Dot ball on last ball rotates strike for over change -> non-striker faces next over
    assert rotate_strike(10, 20, 0, True) == (20, 10)
