"""Typed future-facing getJwks Pokerlost method."""

from __future__ import annotations

from pypokerlost.types import GetJwksResponse, PokerlostOperation

from .base import PokerlostMethod


class GetJwks(PokerlostMethod[GetJwksResponse]):
    """Call getJwks when authService implements the endpoint."""

    operation = PokerlostOperation("getJwks")
    required_scopes = ()
    returning = GetJwksResponse
