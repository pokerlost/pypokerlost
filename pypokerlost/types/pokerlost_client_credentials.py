"""Client credentials used by Pokerlost authorization middleware."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class PokerlostClientCredentials(BaseModel):
    """Secret-safe service credentials supplied through a JSON token payload."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    client_id: Annotated[str, StringConstraints(strict=True, min_length=1)]
    client_secret: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(repr=False)
