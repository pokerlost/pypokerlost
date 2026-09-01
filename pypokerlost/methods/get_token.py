"""Typed getToken Pokerlost method."""

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


def _canonical_scopes(value: object) -> tuple[PokerlostScope, ...]:
    if not isinstance(value, (list, tuple, frozenset)):
        raise ValueError("Requested scopes must be a tuple or JSON array")
    return canonicalize_pokerlost_scopes(value)


class GetToken(PokerlostMethod[PokerlostToken]):
    """Acquire a service token through a public body-only call."""

    operation = PokerlostOperation("getToken")
    required_scopes = ()
    returning = PokerlostToken

    client_id: Annotated[str, StringConstraints(strict=True, min_length=1)]
    client_secret: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(repr=False)
    scopes: Annotated[
        tuple[PokerlostScope, ...],
        BeforeValidator(_canonical_scopes),
    ]
    audience: Annotated[str, StringConstraints(strict=True, min_length=1)]
