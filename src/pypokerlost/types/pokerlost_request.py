"""Public Pokerlost JSON request envelope."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PokerlostRequest[PayloadT](BaseModel):
    """The pure JSON envelope for every Pokerlost business payload."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    payload: PayloadT
