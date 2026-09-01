"""Monotonic token lifecycle state for authorization middleware stores."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .pokerlost_token import PokerlostToken


class PokerlostTokenState(BaseModel):
    """A token and its process-local monotonic expiry instant."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )

    token: PokerlostToken = Field(repr=False)
    expires_at: Annotated[float, Field(strict=True, ge=0.0)]
