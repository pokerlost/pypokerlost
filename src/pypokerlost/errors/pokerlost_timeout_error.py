"""Pokerlost transport timeout error."""

from __future__ import annotations

from .pokerlost_client_error import PokerlostClientError


class PokerlostTimeoutError(PokerlostClientError):
    """Raised when one API attempt exceeds its timeout."""

    operation: str

    def __init__(self, *, operation: str) -> None:
        self.operation = operation
        super().__init__(f"Request timed out; operation={operation!r}")
