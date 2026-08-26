from __future__ import annotations

from dataclasses import dataclass, field

from pypokerlost.methods import BaseMethod


@dataclass(frozen=True, slots=True)
class PreparedRequest:
    """Transport-neutral request produced from a method object."""

    operation: str
    http_method: str
    path: str
    content: bytes = field(repr=False)


class RequestBuilder:
    """Translate declarative method data into a request value."""

    def build(self, method: BaseMethod) -> PreparedRequest:
        method_type = type(method)
        try:
            operation = method_type.__api_method__
        except AttributeError:
            raise TypeError("Concrete methods must declare a non-empty __api_method__") from None
        if not isinstance(operation, str) or not operation.strip():
            raise TypeError("Concrete methods must declare a non-empty __api_method__")

        try:
            http_method = method_type.__http_method__
        except AttributeError:
            raise TypeError("Concrete methods must declare a non-empty __http_method__") from None
        if not isinstance(http_method, str) or not http_method.strip():
            raise TypeError("Concrete methods must declare a non-empty __http_method__")

        return PreparedRequest(
            operation=operation,
            http_method=http_method,
            path=f"/{operation}",
            content=method.model_dump_json(by_alias=False).encode("utf-8"),
        )
