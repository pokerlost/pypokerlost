"""Pokerlost authentication failure."""

from __future__ import annotations

from .pokerlost_api_error import PokerlostAPIError


class PokerlostAuthenticationError(PokerlostAPIError):
    """A 401 or body error identifying invalid/missing authentication."""
