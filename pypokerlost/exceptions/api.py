from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypokerlost.enums import ServiceName
from pypokerlost.exceptions.base import PokerlostError

if TYPE_CHECKING:
    from pypokerlost.methods import PokerlostMethod


class PokerlostAPIError(PokerlostError):
    """Raised when a valid response envelope reports an operation failure."""

    method: PokerlostMethod[Any]
    service: ServiceName
    operation: str
    status_code: int
    error: str
    error_message: str

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        service: ServiceName,
        operation: str,
        status_code: int,
        error: str,
        error_message: str,
    ) -> None:
        self.method = method
        self.service = service
        self.operation = operation
        self.status_code = status_code
        self.error = error
        self.error_message = error_message
        super().__init__(
            f"Pokerlost API error {error!r}: {error_message}; service={service.value!r}; "
            f"operation={operation!r}; status_code={status_code}"
        )


class PokerlostProtocolError(PokerlostAPIError):
    """Raised when HTTP status and a successful envelope contradict each other."""

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
        self.error = "protocol_error"
        self.error_message = "HTTP status contradicts a successful response envelope"
        PokerlostError.__init__(
            self,
            f"Pokerlost protocol error; service={service.value!r}; "
            f"operation={operation!r}; status_code={status_code}",
        )


class PokerlostBadRequestError(PokerlostAPIError):
    """A failed response with HTTP status 400."""


class PokerlostUnauthorizedError(PokerlostAPIError):
    """A failed response with HTTP status 401."""


class PokerlostForbiddenError(PokerlostAPIError):
    """A failed response with HTTP status 403."""


class PokerlostNotFoundError(PokerlostAPIError):
    """A failed response with HTTP status 404."""


class PokerlostConflictError(PokerlostAPIError):
    """A failed response with HTTP status 409."""


class PokerlostEntityTooLargeError(PokerlostAPIError):
    """A failed response with HTTP status 413."""


class PokerlostValidationError(PokerlostAPIError):
    """A failed response with HTTP status 422."""


class PokerlostTooManyRequestsError(PokerlostAPIError):
    """A failed response with HTTP status 429."""


class PokerlostServerError(PokerlostAPIError):
    """A failed response with an HTTP server-error status."""
