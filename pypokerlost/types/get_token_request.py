"""Payload for the public getToken operation."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

from .pokerlost_scope import PokerlostScope, canonicalize_pokerlost_scopes


def _canonical_scopes(value: object) -> tuple[PokerlostScope, ...]:
    if not isinstance(value, (list, tuple, frozenset)):
        raise ValueError("Requested scopes must be a tuple or JSON array")
    return canonicalize_pokerlost_scopes(value)


class GetTokenRequest(BaseModel):
    """Service credentials and exact authority requested from authService."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

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
