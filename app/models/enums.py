import enum

LEGAL_BALLS_PER_OVER = 6


class MatchFormat(str, enum.Enum):
    T20 = "T20"
    ODI = "ODI"
    TEST = "TEST"


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class InningsStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLARED = "declared"


class PlayerRole(str, enum.Enum):
    BATSMAN = "batsman"
    BOWLER = "bowler"
    ALL_ROUNDER = "all_rounder"
    WICKETKEEPER = "wicketkeeper"


class BattingStyle(str, enum.Enum):
    RIGHT_HAND = "right_hand"
    LEFT_HAND = "left_hand"


class BowlingStyle(str, enum.Enum):
    RIGHT_ARM_FAST = "right_arm_fast"
    RIGHT_ARM_MEDIUM = "right_arm_medium"
    RIGHT_ARM_OFF_SPIN = "right_arm_off_spin"
    RIGHT_ARM_LEG_SPIN = "right_arm_leg_spin"
    LEFT_ARM_FAST = "left_arm_fast"
    LEFT_ARM_MEDIUM = "left_arm_medium"
    LEFT_ARM_ORTHODOX = "left_arm_orthodox"
    LEFT_ARM_CHINAMAN = "left_arm_chinaman"


class ExtraType(str, enum.Enum):
    """Wide and no-ball do not count as legal deliveries."""

    WIDE = "wide"
    NO_BALL = "no_ball"
    BYE = "bye"
    LEG_BYE = "leg_bye"


class WicketType(str, enum.Enum):
    BOWLED = "bowled"
    CAUGHT = "caught"
    LBW = "lbw"
    RUN_OUT = "run_out"
    STUMPED = "stumped"
    HIT_WICKET = "hit_wicket"
    CAUGHT_AND_BOWLED = "caught_and_bowled"
    HANDLED_BALL = "handled_ball"
    OBSTRUCTING_FIELD = "obstructing_field"
    RETIRED_OUT = "retired_out"
    TIMED_OUT = "timed_out"
    HIT_BALL_TWICE = "hit_ball_twice"


def format_innings_over_cap(match_format: MatchFormat) -> int | None:
    """Maximum completed overs per innings; None means no hard cap (Test)."""
    caps = {
        MatchFormat.T20: 20,
        MatchFormat.ODI: 50,
        MatchFormat.TEST: None,
    }
    return caps[match_format]


def format_bowler_over_cap(match_format: MatchFormat) -> int | None:
    """Maximum overs a single bowler may bowl; None means no hard cap (Test)."""
    caps = {
        MatchFormat.T20: 4,
        MatchFormat.ODI: 10,
        MatchFormat.TEST: None,
    }
    return caps[match_format]


def is_legal_delivery_extra(extra_type: ExtraType | None) -> bool:
    """Wides and no-balls are re-bowled and do not advance the legal-ball count."""
    return extra_type not in (ExtraType.WIDE, ExtraType.NO_BALL)
