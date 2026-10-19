"""Payload for the public refreshToken operation."""

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


def _canonical_optional_scopes(value: object) -> tuple[PokerlostScopes, ...] | None:
    if value is None:
        return None
    return parse_scope_set(value, field_name="Requested scopes")


class RefreshTokenRequest(BaseModel):
    """Refresh secret, optional exact scopes, and target audience."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    refresh_token: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(repr=False)
    scopes: Annotated[
        tuple[PokerlostScopes, ...] | None,
        BeforeValidator(_canonical_optional_scopes),
    ] = None
    audience: PokerlostAudience
