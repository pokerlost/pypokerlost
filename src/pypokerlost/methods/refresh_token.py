"""Typed refreshToken Pokerlost method."""

from __future__ import annotations

from typing import Annotated, ClassVar

from pydantic import BeforeValidator, Field, StringConstraints

from pypokerlost.enums import PokerlostScopes
from pypokerlost.types import PokerlostAudience, PokerlostOperation, PokerlostToken
from pypokerlost.types._scope_set import parse_scope_set

from .base import PokerlostMethod


def _canonical_optional_scopes(value: object) -> tuple[PokerlostScopes, ...] | None:
    if value is None:
        return None
    return parse_scope_set(value, field_name="Requested scopes")


class RefreshToken(PokerlostMethod[PokerlostToken]):
    """Refresh a token through an explicit public call."""

    operation = PokerlostOperation("refreshToken")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = None
    returning = PokerlostToken

    refresh_token: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(repr=False)
    scopes: Annotated[
        tuple[PokerlostScopes, ...] | None,
        BeforeValidator(_canonical_optional_scopes),
    ] = None
    audience: PokerlostAudience
