"""Pokerlost transport connection error."""

from __future__ import annotations

from .pokerlost_client_error import PokerlostClientError


class PokerlostConnectionError(PokerlostClientError):
    """Raised when the transport cannot complete an API call."""

    operation: str

    def __init__(self, *, operation: str) -> None:
        self.operation = operation
        super().__init__(f"Connection failed; operation={operation!r}")
