"""Canonical Pokerlost JSON response envelope."""

from __future__ import annotations

from math import isfinite
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class PokerlostResponse[ResultT](BaseModel):
    """Represent exactly one successful or failed Pokerlost API response."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )

    ok: bool
    result: ResultT | None = None
    error: str | None = None
    error_message: str | None = None
    retry_after: float | None = None

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        """Reject combinations that cannot exist in the body protocol."""
        if self.retry_after is not None and (
            not isfinite(self.retry_after) or self.retry_after < 0.0
        ):
            raise ValueError("retry_after must be finite and non-negative")
        if self.ok:
            if any(
                value is not None for value in (self.error, self.error_message, self.retry_after)
            ):
                raise ValueError("Successful responses cannot contain failure metadata")
            return self
        if self.result is not None:
            raise ValueError("Failed responses cannot contain a result")
        if self.error is None or not self.error:
            raise ValueError("Failed responses require a stable error code")
        return self
