"""Payload for the public getToken operation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
)

from pypokerlost.enums import PokerlostScopes

from ._scope_set import parse_scope_set
from .pokerlost_audience import PokerlostAudience


def _canonical_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Requested scopes")


class GetTokenRequest(BaseModel):
    """Service credentials and exact authority requested from authService."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    client_id: UUID = Field(strict=False)
    client_secret: SecretStr = Field(min_length=1, repr=False)
    scopes: Annotated[
        tuple[PokerlostScopes, ...],
        BeforeValidator(_canonical_scopes),
    ] = Field(min_length=1)
    audience: PokerlostAudience
