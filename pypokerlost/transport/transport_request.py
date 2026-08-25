from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType

from pypokerlost.types.json_value import JsonValue

type QueryParameterValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True, init=False)
class TransportRequest:
    """An immutable HTTP request value understood by SDK transports."""

    method: str
    path: str
    query: Mapping[str, QueryParameterValue]
    _json: JsonValue | None = field(repr=False)
    headers: Mapping[str, str]

    def __init__(
        self,
        method: str,
        path: str,
        query: Mapping[str, QueryParameterValue] | None = None,
        json: JsonValue | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        normalized_method = method.strip().upper()
        if not normalized_method:
            raise ValueError("HTTP method must not be empty")
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Transport request path must start with exactly one slash")
        if "?" in path or "#" in path:
            raise ValueError("Query parameters and fragments do not belong in request path")

        object.__setattr__(self, "method", normalized_method)
        object.__setattr__(self, "path", path)
        object.__setattr__(
            self,
            "query",
            MappingProxyType(dict({} if query is None else query)),
        )
        object.__setattr__(self, "_json", deepcopy(json))
        object.__setattr__(
            self,
            "headers",
            MappingProxyType(dict({} if headers is None else headers)),
        )

    @property
    def json(self) -> JsonValue | None:
        """Return a defensive copy of the immutable request-body snapshot."""
        return deepcopy(self._json)
