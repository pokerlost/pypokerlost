"""Typed refreshToken Pokerlost method."""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, Field, StringConstraints

from pypokerlost.types import (
    PokerlostOperation,
    PokerlostScope,
    PokerlostToken,
    canonicalize_pokerlost_scopes,
)

from .base import PokerlostMethod


def _canonical_optional_scopes(value: object) -> tuple[PokerlostScope, ...] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple, frozenset)):
        raise ValueError("Requested scopes must be null, a tuple, or a JSON array")
    return canonicalize_pokerlost_scopes(value)


class RefreshToken(PokerlostMethod[PokerlostToken]):
    """Refresh a token through a public body-only call."""

    operation = PokerlostOperation("refreshToken")
    required_scopes = ()
    returning = PokerlostToken

    refresh_token: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(repr=False)
    scopes: Annotated[
        tuple[PokerlostScope, ...] | None,
        BeforeValidator(_canonical_optional_scopes),
    ] = None
    audience: Annotated[str, StringConstraints(strict=True, min_length=1)]
