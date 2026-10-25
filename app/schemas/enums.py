from enum import Enum

class MatchFormat(str, Enum):
    T20 = "t20"
    ODI = "odi"

    @property
    def max_overs(self) -> int:
        match self:
            case MatchFormat.T20:
                return 20
            case MatchFormat.ODI:
                return 50

    @property
    def max_bowler_overs(self) -> int:
        match self:
            case MatchFormat.T20:
                return 4
            case MatchFormat.ODI:
                return 10

    @property
    def total_innings(self) -> int:
        return 2

class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    TOSS_DONE = "toss_done"
    LIVE = "live"
    INNINGS_BREAK = "innings_break"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

class InningsStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

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
    RIGHT_ARM_MEDIUM = "right-arm medium"
    LEFT_ARM_MEDIUM = "left-arm medium"
    RIGHT_ARM_SPIN = "right-arm spin"
    LEFT_ARM_SPIN = "left-arm spin"

class WicketType(str, Enum):
    BOWLED = "bowled"
    CAUGHT = "caught"
    LBW = "lbw"
    RUN_OUT = "run_out"
    STUMPED = "stumped"
    HIT_WICKET = "hit_wicket"
    CAUGHT_AND_BOWLED = "caught_and_bowled"

class ExtraType(str, Enum):
    WIDE = "wide"
    NOBALL = "noball"
    BYE = "bye"
    LEGBYE = "leg-bye"

