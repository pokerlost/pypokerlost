"""Persistent shared access-token state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field

from .pokerlost_token import PokerlostToken


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


class PokerlostStoredToken(BaseModel):
    """Encrypted-at-rest token data with absolute UTC expiry and CAS version."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    token: PokerlostToken = Field(repr=False)
    expires_at: Annotated[AwareDatetime, AfterValidator(_as_utc)]
    version: Annotated[int, Field(strict=True, gt=0)]
