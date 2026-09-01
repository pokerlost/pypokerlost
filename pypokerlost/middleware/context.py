"""Immutable public metadata for one outbound API middleware call."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pypokerlost.client.request import RequestOptions
from pypokerlost.types import APIOperation, HTTPMethod


class APIMiddlewareContext(BaseModel):
    """Expose safe call metadata and transport options without the request body."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    operation: APIOperation
    http_method: HTTPMethod
    options: RequestOptions
