from ._safe_metadata import safe_detail, safe_operation
from .pokerlost_error import PokerLostError


class ApplicationError(PokerLostError):
    """Raised when a valid application response reports a failed operation."""

    error: str
    error_message: str
    operation: str
    status_code: int

    def __init__(
        self,
        *,
        error: str,
        error_message: str,
        operation: str,
        status_code: int,
    ) -> None:
        self.error = error
        self.error_message = error_message
        self.operation = operation
        self.status_code = status_code

        safe_error = safe_detail(error) or ""
        safe_error_message = safe_detail(error_message) or ""
        safe_method_operation = safe_operation(operation) or ""
        super().__init__(
            f"Application error {safe_error!r}: {safe_error_message}; "
            f"operation={safe_method_operation!r}; status_code={status_code}"
        )
