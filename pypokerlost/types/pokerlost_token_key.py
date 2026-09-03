"""Persistent token-store identity key."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints

from pypokerlost.enums import PokerlostScopes

from ._scope_set import parse_scope_set
from .pokerlost_audience import PokerlostAudience


def _parse_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Token key scopes")


class PokerlostTokenKey(BaseModel):
    """Separate shared token state by client, audience, and exact scopes."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    client_id: Annotated[str, StringConstraints(strict=True, min_length=1)]
    audience: PokerlostAudience
    scopes: Annotated[tuple[PokerlostScopes, ...], BeforeValidator(_parse_scopes)]
