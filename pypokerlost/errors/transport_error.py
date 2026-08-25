from ._safe_metadata import safe_detail, safe_operation
from .pokerlost_error import PokerLostError


class TransportError(PokerLostError):
    """Raised when the transport cannot complete an HTTP operation."""

    operation: str | None
    detail: str | None

    def __init__(self, operation: str | None = None, detail: str | None = None) -> None:
        self.operation = safe_operation(operation)
        self.detail = safe_detail(detail)

        message = "HTTP transport failed"
        if self.operation is not None:
            message = f"{message}; operation={self.operation!r}"
        if self.detail is not None:
            message = f"{message}; detail={self.detail}"
        super().__init__(message)
