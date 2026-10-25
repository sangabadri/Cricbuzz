class CricketDomainError(Exception):
    """Base exception for all cricket domain rule violations."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PayloadValidationError(CricketDomainError):
    """Raised when delivery payload attributes violate cricket constraints."""
    pass


class CreaseViolationError(CricketDomainError):
    """Raised when crease continuity or non-rebatting invariants are violated."""
    pass


class BowlerRuleError(CricketDomainError):
    """Raised when bowler quota, consecutive over, or mid-over continuity rules are violated."""
    pass


class OverProgressionError(CricketDomainError):
    """Raised when over progression or ball numbering invariants are violated."""
    pass


class MatchStateError(CricketDomainError):
    """Raised when an operation cannot be performed due to current match/innings status."""
    pass


class HistoricalEditLockedError(CricketDomainError):
    """Raised when editing or undoing a delivery is locked due to match completion or over closure."""
    pass


class SquadValidationError(CricketDomainError):
    """Raised when squad submission or playing XI constraints are violated."""
    pass
