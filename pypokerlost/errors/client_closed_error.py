from ._safe_metadata import safe_operation
from .pokerlost_error import PokerLostError


class ClientClosedError(PokerLostError):
    """Raised when an operation is attempted with a closed client."""

    operation: str | None

    def __init__(self, operation: str | None = None) -> None:
        self.operation = safe_operation(operation)
        message = "Client is closed"
        if self.operation is not None:
            message = f"{message}; operation={self.operation!r}"
        super().__init__(message)
