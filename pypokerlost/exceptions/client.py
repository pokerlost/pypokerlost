"""Client execution exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypokerlost.exceptions.base import PokerlostError

if TYPE_CHECKING:
    from pypokerlost.methods import PokerlostMethod


class ClientError(PokerlostError):
    """Base class for client execution failures."""


class ClientContextError(ClientError):
    """Raised when an awaited method cannot resolve a client."""

    def __init__(self) -> None:
        super().__init__(
            "No Client is available; use await client(method), await method.as_(client), "
            "or await method inside an Application/client lifecycle"
        )


class ClientStateError(ClientError):
    """Raised when a client async-context entry is invalid."""

    def __init__(self, message: str = "Client async context is already active") -> None:
        super().__init__(message)


class ClientRequestError(ClientError):
    """Raised when local request preparation or transport configuration is invalid."""

    operation: str | None

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        operation: str | None = None,
    ) -> None:
        self.operation = operation
        if operation is None:
            super().__init__("Request preparation failed")
        else:
            super().__init__(f"Request preparation failed; operation={operation!r}")


class ClientDecodeError(ClientError):
    """Raised when a response violates the declared wire or result contract."""

    operation: str
    status_code: int
    retry_after: float | None

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        operation: str,
        status_code: int,
        retry_after: float | None = None,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(
            f"Response decoding failed; operation={operation!r}; status_code={status_code}"
        )


class ClientConnectionError(ClientError):
    """Raised when the HTTP transport cannot complete a request."""

    operation: str

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        operation: str,
    ) -> None:
        self.operation = operation
        super().__init__(f"Connection failed; operation={operation!r}")


class ClientTimeoutError(ClientError):
    """Raised when an HTTP request exceeds its configured timeout."""

    operation: str

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        operation: str,
    ) -> None:
        self.operation = operation
        super().__init__(f"Request timed out; operation={operation!r}")
