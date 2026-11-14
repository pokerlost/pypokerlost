"""Persistent shared access-token state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field

from .pokerlost_token import PokerlostToken
from .pokerlost_token_key import PokerlostTokenKey


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


class PokerlostStoredToken(BaseModel):
    """Encrypted-at-rest state with UTC expiry, CAS version, and optional local key provenance."""

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

    key: PokerlostTokenKey | None = Field(default=None, exclude_if=lambda value: value is None)
