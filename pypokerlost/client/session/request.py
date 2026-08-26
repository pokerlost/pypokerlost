from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pypokerlost.methods import BaseMethod
from pypokerlost.types import JsonValue

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


@dataclass(frozen=True, slots=True)
class PreparedRequest:
    """Transport-neutral request produced from a method object."""

    method: str
    path: str
    json: JsonValue = field(repr=False)


class RequestBuilder:
    """Translate declarative method data into a request value."""

    def build(self, client: Client, method: BaseMethod) -> PreparedRequest:
        method_type = type(method)
        api_method = getattr(method_type, "__api_method__", None)
        if not isinstance(api_method, str) or not api_method.strip():
            raise TypeError("Concrete methods must declare a non-empty __api_method__")

        http_method = getattr(method_type, "__http_method__", None)
        if not isinstance(http_method, str) or not http_method.strip():
            raise TypeError("Concrete methods must declare a non-empty __http_method__")

        return PreparedRequest(
            method=http_method,
            path=f"/{api_method}",
            json=method.model_dump(mode="json", by_alias=False),
        )
