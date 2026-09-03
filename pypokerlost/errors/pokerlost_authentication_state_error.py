"""Missing or unusable shared authentication state."""

from __future__ import annotations

from .pokerlost_client_error import PokerlostClientError


class PokerlostAuthenticationStateError(PokerlostClientError):
    """Raised locally when a protected call cannot obtain usable stored state."""

    operation: str

    def __init__(self, message: str, *, operation: str) -> None:
        self.operation = operation
        super().__init__(f"{message}; operation={operation!r}")
