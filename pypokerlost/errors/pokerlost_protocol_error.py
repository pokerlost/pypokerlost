"""Pokerlost response protocol error."""

from __future__ import annotations

from .pokerlost_client_error import PokerlostClientError


class PokerlostProtocolError(PokerlostClientError):
    """Raised when a response body violates the Pokerlost JSON protocol."""

    operation: str
    status_code: int | None

    def __init__(self, *, operation: str, status_code: int | None = None) -> None:
        self.operation = operation
        self.status_code = status_code
        status = "unknown" if status_code is None else str(status_code)
        super().__init__(
            f"Pokerlost response protocol violation; operation={operation!r}; status_code={status}"
        )
