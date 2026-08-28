"""PokerLost API response envelope."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Response[ResultT](BaseModel):
    """Validate one PokerLost success or failure response."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    ok: bool = Field(description="Whether the operation completed successfully.")
    result: ResultT | None = Field(default=None)
    error: str | None = Field(default=None)
    error_message: str | None = Field(default=None)

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        """Require mutually exclusive success and failure fields."""
        if self.ok:
            if self.error is not None or self.error_message is not None:
                raise ValueError("Successful responses cannot contain error metadata")
            return self
        if self.result is not None:
            raise ValueError("Failed responses cannot contain a result")
        if self.error is None or self.error_message is None:
            raise ValueError("Failed responses require error metadata")
        return self
