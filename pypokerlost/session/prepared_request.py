from __future__ import annotations

from collections.abc import Mapping
from json import dumps, loads
from types import MappingProxyType
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pypokerlost.types import HttpMethod, JsonValue

type QueryParameterValue = str | int | float | bool | None


class PreparedRequest(BaseModel):
    """Immutable HTTP request produced by the shared request builder."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )

    method: HttpMethod
    path: str
    query: Mapping[str, QueryParameterValue] = Field(default_factory=dict)
    headers: Mapping[str, str] = Field(default_factory=dict)
    body: bytes | None = Field(default=None, repr=False)

    def __init__(
        self,
        method: HttpMethod,
        path: str,
        query: Mapping[str, QueryParameterValue] | None = None,
        json_body: JsonValue | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        body = (
            None
            if json_body is None
            else dumps(
                json_body,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
        super().__init__(
            method=method,
            path=path,
            query={} if query is None else query,
            headers={} if headers is None else headers,
            body=body,
        )

    @field_validator("path")
    @classmethod
    def validate_path(cls, path: str) -> str:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Prepared request path must start with exactly one slash")
        if "?" in path or "#" in path:
            raise ValueError("Query parameters and fragments do not belong in request path")
        return path

    @field_validator("query", mode="after")
    @classmethod
    def freeze_query(
        cls,
        query: Mapping[str, QueryParameterValue],
    ) -> Mapping[str, QueryParameterValue]:
        return MappingProxyType(dict(query))

    @field_validator("headers", mode="after")
    @classmethod
    def freeze_headers(cls, headers: Mapping[str, str]) -> Mapping[str, str]:
        return MappingProxyType(dict(headers))

    @property
    def json_body(self) -> JsonValue | None:
        """Return a defensive copy of the prepared request body."""
        if self.body is None:
            return None
        return cast(JsonValue, loads(self.body))
