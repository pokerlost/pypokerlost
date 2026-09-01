"""Pokerlost SDK configuration failure."""

from __future__ import annotations

from .pokerlost_client_error import PokerlostClientError


class PokerlostConfigurationError(PokerlostClientError):
    """Raised before I/O when a required client capability is absent or invalid."""

    operation: str | None

    def __init__(self, message: str, *, operation: str | None = None) -> None:
        self.operation = operation
        suffix = "" if operation is None else f"; operation={operation!r}"
        super().__init__(f"{message}{suffix}")
