"""Base Pokerlost client error."""

from __future__ import annotations

from .pokerlost_error import PokerlostError


class PokerlostClientError(PokerlostError):
    """Base class for safe client-side failures."""
