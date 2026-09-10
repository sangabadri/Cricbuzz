from enum import Enum

class MatchFormat(str, Enum):
    T20 = "t20"
    ODI = "odi"
    TEST = "test"

class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    TOSS_DONE = "toss_done"
    LIVE = "live"
    INNINGS_BREAK = "innings_break"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

class TossDecision(str, Enum):
    BAT = "bat"
    BOWL = "bowl"

class Role(str, Enum):
    BATSMAN = "batsman"
    BOWLER = "bowler"
    ALLROUNDER = "all-rounder"
    WICKETKEEPER = "wicketkeeper"
    
class BattingStyle(str, Enum):
    RIGHT_HANDED = "right-handed batsman"
    LEFT_HANDED = "left-handed batsman"

class BowlingStyle(str, Enum):
    RIGHT_ARM_FAST = "right-arm fast"
    LEFT_ARM_FAST = "left-arm fast"
    RIGHT_ARM_FAST_MEDIUM = "right-arm fast-medium"
    LEFT_ARM_FAST_MEDIUM = "left-arm fast-medium"
    RIGHT_ARM_MEDIUM = "right-arm medium"
    LEFT_ARM_MEDIUM = "left-arm medium"
    RIGHT_ARM_OFF_BREAK = "right-arm off-break"
    LEFT_ARM_ORTHODOX = "left-arm orthodox"
    RIGHT_ARM_LEG_BREAK = "right-arm leg-break"
    LEFT_ARM_CHINAMAN = "left-arm chinaman"

class WicketType(str, Enum):
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

class ExtraType(str, Enum):
    WIDE = "wide"
    NOBALL = "noball"
    BYE = "bye"
    LEGBYE = "leg-bye"

