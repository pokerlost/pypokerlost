"""Pokerlost authorization failure."""

from __future__ import annotations

from .pokerlost_api_error import PokerlostAPIError


class PokerlostAuthorizationError(PokerlostAPIError):
    """A 403 or body error identifying insufficient exact scopes."""
