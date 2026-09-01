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

from .pokerlost_scope import PokerlostScope, canonicalize_pokerlost_scopes


def _canonical_optional_scopes(value: object) -> tuple[PokerlostScope, ...] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple, frozenset)):
        raise ValueError("Requested scopes must be null, a tuple, or a JSON array")
    return canonicalize_pokerlost_scopes(value)


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
        tuple[PokerlostScope, ...] | None,
        BeforeValidator(_canonical_optional_scopes),
    ] = None
    audience: Annotated[str, StringConstraints(strict=True, min_length=1)]
