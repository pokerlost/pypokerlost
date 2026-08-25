"""Shared public application response envelope."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from .response_model import ResponseModel


class ApplicationResponse[ResultT](ResponseModel):
    """Single success and failure envelope for every public operation."""

    ok: bool = Field(description="Whether the operation completed successfully.")
    result: ResultT | None = Field(default=None, description="Typed successful result.")
    error: str | None = Field(default=None, description="Stable machine-readable error code.")
    error_message: str | None = Field(default=None, description="Safe public error message.")

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
