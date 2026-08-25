"""Public response model configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ResponseModel(BaseModel):
    """Strict immutable base for application-owned API responses."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )
