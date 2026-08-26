class PokerLostError(Exception):
    """Base class for expected SDK failures."""


class ClientContextError(PokerLostError):
    """Raised when a method has no task-local current client."""

    def __init__(self) -> None:
        super().__init__(
            "No current Client is installed; pass a client to execute() or use client.as_current()."
        )


class ClientClosedError(PokerLostError):
    """Raised when an operation is attempted with a closed client."""

    operation: str | None

    def __init__(self, operation: str | None = None) -> None:
        self.operation = operation
        message = "Client is closed"
        if operation is not None:
            message = f"{message}; operation={operation!r}"
        super().__init__(message)


class ClientStateError(PokerLostError):
    """Raised when a client lifecycle operation is invalid for its current state."""


class TransportError(PokerLostError):
    """Raised when the HTTP transport cannot complete an operation."""

    operation: str | None

    def __init__(self, operation: str | None = None) -> None:
        self.operation = operation
        message = "HTTP transport failed"
        if operation is not None:
            message = f"{message}; operation={operation!r}"
        super().__init__(message)


class ApplicationError(PokerLostError):
    """Raised when a valid application envelope reports a failed operation."""

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
        super().__init__(
            f"Application error {error!r}: {error_message}; "
            f"operation={operation!r}; status_code={status_code}"
        )


class UnexpectedStatusError(PokerLostError):
    """Raised when an HTTP status cannot be handled by an operation contract."""

    status_code: int
    operation: str | None

    def __init__(self, status_code: int, *, operation: str | None = None) -> None:
        self.status_code = status_code
        self.operation = operation
        message = f"Unexpected HTTP status {status_code}"
        if operation is not None:
            message = f"{message}; operation={operation!r}"
        super().__init__(message)


class ResponseDecodeError(PokerLostError):
    """Raised when a response violates its wire contract."""

    operation: str | None
    status_code: int | None

    def __init__(
        self,
        operation: str | None = None,
        *,
        status_code: int | None = None,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        message = "Response decoding failed"
        if operation is not None:
            message = f"{message}; operation={operation!r}"
        if status_code is not None:
            message = f"{message}; status_code={status_code}"
        super().__init__(message)


__all__ = (
    "ApplicationError",
    "ClientClosedError",
    "ClientContextError",
    "ClientStateError",
    "PokerLostError",
    "ResponseDecodeError",
    "TransportError",
    "UnexpectedStatusError",
)
