from ._safe_metadata import safe_detail, safe_operation
from .pokerlost_error import PokerLostError


class ResponseDecodeError(PokerLostError):
    """Raised when a successful response violates the shared response contract."""

    operation: str | None
    status_code: int | None
    detail: str | None

    def __init__(
        self,
        operation: str | None = None,
        *,
        status_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        self.operation = safe_operation(operation)
        self.status_code = status_code
        self.detail = safe_detail(detail)

        message = "Response decoding failed"
        if self.operation is not None:
            message = f"{message}; operation={self.operation!r}"
        if status_code is not None:
            message = f"{message}; status_code={status_code}"
        if self.detail is not None:
            message = f"{message}; detail={self.detail}"
        super().__init__(message)
