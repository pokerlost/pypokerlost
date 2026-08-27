from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypokerlost.enums import ServiceName
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

    def __init__(self) -> None:
        super().__init__("Client async context is already active")


class ClientDecodeError(ClientError):
    """Raised when a response violates the declared wire or result contract."""

    method: PokerlostMethod[Any]
    service: ServiceName
    operation: str
    status_code: int

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        service: ServiceName,
        operation: str,
        status_code: int,
    ) -> None:
        self.method = method
        self.service = service
        self.operation = operation
        self.status_code = status_code
        super().__init__(
            f"Response decoding failed; service={service.value!r}; "
            f"operation={operation!r}; status_code={status_code}"
        )


class ClientConnectionError(ClientError):
    """Raised when the HTTP transport cannot complete a request."""

    method: PokerlostMethod[Any]
    service: ServiceName
    operation: str

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        service: ServiceName,
        operation: str,
    ) -> None:
        self.method = method
        self.service = service
        self.operation = operation
        super().__init__(f"Connection failed; service={service.value!r}; operation={operation!r}")


class ClientTimeoutError(ClientError):
    """Raised when an HTTP request exceeds its configured timeout."""

    method: PokerlostMethod[Any]
    service: ServiceName
    operation: str

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        service: ServiceName,
        operation: str,
    ) -> None:
        self.method = method
        self.service = service
        self.operation = operation
        super().__init__(f"Request timed out; service={service.value!r}; operation={operation!r}")
