from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypokerlost.exceptions.base import PokerlostError

if TYPE_CHECKING:
    from pypokerlost.methods import PokerlostMethod


class PokerlostAPIError(PokerlostError):
    """Raised when a valid response envelope reports an operation failure."""

    operation: str
    status_code: int
    error: str
    error_message: str

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        operation: str,
        status_code: int,
        error: str,
        error_message: str,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        self.error = error
        self.error_message = error_message
        super().__init__(
            f"Pokerlost API error {error!r}: {error_message}; "
            f"operation={operation!r}; status_code={status_code}"
        )


class PokerlostProtocolError(PokerlostError):
    """Raised when HTTP status and a successful envelope contradict each other."""

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        operation: str,
        status_code: int,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        super().__init__(
            f"Pokerlost protocol error; operation={operation!r}; status_code={status_code}",
        )
