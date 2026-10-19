"""Result type for the future-facing getJwks operation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .json import JSONValue


class GetJwksResponse(BaseModel):
    """A JSON Web Key Set represented without verification behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
    )

    keys: tuple[dict[str, JSONValue], ...]
