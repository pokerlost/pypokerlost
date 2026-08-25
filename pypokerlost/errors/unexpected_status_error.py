from ._safe_metadata import safe_operation, safe_response_excerpt
from .pokerlost_error import PokerLostError


class UnexpectedStatusError(PokerLostError):
    """Raised when a response has a non-success HTTP status."""

    status_code: int
    operation: str | None
    response_excerpt: str

    def __init__(
        self,
        status_code: int,
        *,
        operation: str | None = None,
        response_body: bytes | str = b"",
    ) -> None:
        self.status_code = status_code
        self.operation = safe_operation(operation)
        self.response_excerpt = safe_response_excerpt(response_body)

        message = f"Unexpected HTTP status {status_code}"
        if self.operation is not None:
            message = f"{message}; operation={self.operation!r}"
        if self.response_excerpt:
            message = f"{message}; response_excerpt={self.response_excerpt!r}"
        super().__init__(message)
