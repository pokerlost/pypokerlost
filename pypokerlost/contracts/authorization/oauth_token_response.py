"""Canonical OAuth2 token operation result."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from pypokerlost.types import format_oauth_scope_string, parse_oauth_scope_string

from .enums import OAuthTokenType


def _canonicalize_scope_string(value: str) -> str:
    return format_oauth_scope_string(parse_oauth_scope_string(value))


class OAuthTokenResponse(BaseModel):
    """Bearer token data carried by ``ApplicationResponse.result``."""

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
    refresh_token: (
        Annotated[
            str,
            StringConstraints(strict=True, min_length=1),
        ]
        | None
    ) = Field(
        default=None,
        repr=False,
        exclude_if=lambda value: value is None,
    )
    token_type: OAuthTokenType
    expires_in: Annotated[int, Field(strict=True, gt=0)]
    scope: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
        AfterValidator(_canonicalize_scope_string),
    ]
