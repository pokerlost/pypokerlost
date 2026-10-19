"""Typed future-facing getJwks Pokerlost method."""

from __future__ import annotations

from typing import ClassVar

from pypokerlost.enums import PokerlostScopes
from pypokerlost.types import GetJwksResponse, PokerlostOperation

from .base import PokerlostMethod


class GetJwks(PokerlostMethod[GetJwksResponse]):
    """Call getJwks when authService implements the endpoint."""

    operation = PokerlostOperation("getJwks")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = None
    returning = GetJwksResponse
