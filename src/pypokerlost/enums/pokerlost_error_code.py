"""Common authentication error codes owned by the Pokerlost protocol."""

from __future__ import annotations

from enum import StrEnum


class PokerlostErrorCode(StrEnum):
    """Shared protocol vocabulary; service-owned error codes remain open strings."""

    AUTHENTICATION_REQUIRED = "POKERLOST_AUTHENTICATION_REQUIRED"
    ACCESS_TOKEN_INVALID = "POKERLOST_ACCESS_TOKEN_INVALID"
    ACCESS_TOKEN_EXPIRED = "POKERLOST_ACCESS_TOKEN_EXPIRED"
    INSUFFICIENT_SCOPE = "POKERLOST_INSUFFICIENT_SCOPE"
