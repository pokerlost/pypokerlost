"""Validated client request passed to a session."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pypokerlost.types import APIOperation, HTTPMethod, JSONValue


class Request(BaseModel):
    """One validated API request before concrete transport execution."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    method: APIOperation
    http_method: HTTPMethod
    data: dict[str, JSONValue] = Field(repr=False)
    headers: tuple[tuple[str, str], ...] = Field(default=(), repr=False, exclude=True)
