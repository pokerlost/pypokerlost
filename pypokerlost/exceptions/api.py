"""PokerLost API and protocol exceptions."""

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
    retry_after: float | None

    def __init__(
        self,
        *,
        method: PokerlostMethod[Any],
        operation: str,
        status_code: int,
        error: str,
        error_message: str,
        retry_after: float | None = None,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        self.error = error
        self.error_message = error_message
        self.retry_after = retry_after
        super().__init__(
            f"PokerLost API error {error!r}: {error_message}; "
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
        retry_after: float | None = None,
    ) -> None:
        self.operation = operation
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(
            f"PokerLost protocol error; operation={operation!r}; status_code={status_code}",
        )
