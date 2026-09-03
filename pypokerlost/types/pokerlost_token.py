"""Canonical Pokerlost token result data."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

from pypokerlost.enums import PokerlostScopes

from ._scope_set import parse_scope_set
from .pokerlost_audience import PokerlostAudience


def _canonical_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Token scopes")


class PokerlostToken(BaseModel):
    """Secret-safe token data without network or lifecycle behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    access_token: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(repr=False)
    refresh_token: Annotated[str, StringConstraints(strict=True, min_length=1)] | None = Field(
        default=None, repr=False
    )
    expires_in: Annotated[int, Field(strict=True, gt=0)]
    scopes: Annotated[
        tuple[PokerlostScopes, ...],
        BeforeValidator(_canonical_scopes),
    ]
    audience: PokerlostAudience
