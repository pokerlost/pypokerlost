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

from .pokerlost_scope import PokerlostScope, canonicalize_pokerlost_scopes


def _canonical_scopes(value: object) -> tuple[PokerlostScope, ...]:
    if not isinstance(value, (list, tuple, frozenset)):
        raise ValueError("Token scopes must be an immutable tuple or a JSON array")
    return canonicalize_pokerlost_scopes(value)


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
        tuple[PokerlostScope, ...],
        BeforeValidator(_canonical_scopes),
    ]
    audience: Annotated[str, StringConstraints(strict=True, min_length=1)]
