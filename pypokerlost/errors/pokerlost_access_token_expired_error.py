"""Canonical expired access-token API failure."""

from __future__ import annotations

from .pokerlost_authentication_error import PokerlostAuthenticationError


class PokerlostAccessTokenExpiredError(PokerlostAuthenticationError):
    """The only API failure that permits one reactive refresh and replay."""
