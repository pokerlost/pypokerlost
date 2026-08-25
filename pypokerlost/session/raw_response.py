from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RawResponse(BaseModel):
    """Immutable buffered response independent of an HTTP implementation."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )

    status_code: int
    headers: Mapping[str, str]
    body: bytes = Field(repr=False)

    @field_validator("headers", mode="after")
    @classmethod
    def freeze_headers(cls, headers: Mapping[str, str]) -> Mapping[str, str]:
        return MappingProxyType(dict(headers))
