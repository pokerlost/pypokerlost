"""Typed request construction for API operations."""

from __future__ import annotations

from pydantic import TypeAdapter, ValidationError

from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import APIOperation, HTTPMethod

from .request import Request
from .request_options import RequestOptions

_DEFAULT_HEADERS = (
    ("Content-Type", "application/json"),
    ("Accept", "application/json"),
)


class RequestBuilder:
    """Build a validated transport-independent request from a typed method."""

    def __init__(self) -> None:
        self._operation_adapter: TypeAdapter[APIOperation] = TypeAdapter(APIOperation)
        self._http_method_adapter: TypeAdapter[HTTPMethod] = TypeAdapter(HTTPMethod)

    def build[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        options: RequestOptions | None = None,
    ) -> Request:
        operation = self._parse_operation(method)
        http_method = self._parse_http_method(method)
        data = method.model_dump(
            mode="json",
            by_alias=False,
            exclude_unset=True,
        )

        request_options = options if options is not None else RequestOptions()
        custom_header_names = {name.casefold() for name, _ in request_options.headers}
        headers = (
            tuple(
                (name, value)
                for name, value in _DEFAULT_HEADERS
                if name.casefold() not in custom_header_names
            )
            + request_options.headers
        )

        return Request(
            method=operation,
            http_method=http_method,
            data=data,
            headers=headers,
        )

    def _parse_operation[ResultT](
        self,
        method: PokerlostMethod[ResultT],
    ) -> APIOperation:
        try:
            return self._operation_adapter.validate_python(method.__api_method__)
        except AttributeError, ValidationError:
            pass
        raise TypeError(
            "Concrete methods must declare a lowercase namespace.method __api_method__",
        ) from TypeError("API operation validation failed")

    def _parse_http_method[ResultT](
        self,
        method: PokerlostMethod[ResultT],
    ) -> HTTPMethod:
        try:
            return self._http_method_adapter.validate_python(
                method.__http_method__,
            )
        except AttributeError, ValidationError:
            pass
        raise TypeError(
            "Concrete methods must declare __http_method__ as GET, POST, PUT, PATCH, or DELETE",
        ) from TypeError("HTTP method validation failed")
