from abc import ABC, abstractmethod
from app.schemas.enums import MatchFormat


class FormatRules(ABC):
    """Abstract strategy defining match-level overs and bowler quota rules."""

    @property
    @abstractmethod
    def max_overs(self) -> int:
        """Maximum overs permitted per innings."""
        pass

    @property
    @abstractmethod
    def max_bowler_overs(self) -> int:
        """Maximum overs permitted per individual bowler."""
        pass


class T20FormatRules(FormatRules):
    @property
    def max_overs(self) -> int:
        return 20

    @property
    def max_bowler_overs(self) -> int:
        return 4


class ODIFormatRules(FormatRules):
    @property
    def max_overs(self) -> int:
        return 50

    @property
    def max_bowler_overs(self) -> int:
        return 10


class CustomFormatRules(FormatRules):
    def __init__(self, max_overs: int, max_bowler_overs: int):
        self._max_overs = max_overs
        self._max_bowler_overs = max_bowler_overs

    @property
    def max_overs(self) -> int:
        return self._max_overs

    @property
    def max_bowler_overs(self) -> int:
        return self._max_bowler_overs


def get_format_rules(match_format: MatchFormat | str) -> FormatRules:
    """Factory method resolving the format rules strategy."""
    val = match_format.value if isinstance(match_format, MatchFormat) else str(match_format).lower()
    if val == MatchFormat.T20.value:
        return T20FormatRules()
    elif val == MatchFormat.ODI.value:
        return ODIFormatRules()
    raise ValueError(f"Unsupported match format: {match_format}")
