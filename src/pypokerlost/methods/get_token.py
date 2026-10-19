"""Typed getToken Pokerlost method."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import BeforeValidator, Field, StringConstraints

from pypokerlost.enums import PokerlostScopes
from pypokerlost.types import PokerlostAudience, PokerlostOperation, PokerlostToken
from pypokerlost.types._scope_set import parse_scope_set

from .base import PokerlostMethod


def _canonical_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Requested scopes")


class GetToken(PokerlostMethod[PokerlostToken]):
    """Acquire a service token through an explicit public call."""

    operation = PokerlostOperation("getToken")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = None
    returning = PokerlostToken

    client_id: UUID
    client_secret: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(repr=False)
    scopes: Annotated[
        tuple[PokerlostScopes, ...],
        BeforeValidator(_canonical_scopes),
    ] = Field(min_length=1)
    audience: PokerlostAudience
