from __future__ import annotations

from pydantic import TypeAdapter, ValidationError

from pypokerlost.environment import APIServer
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import HTTPMethod, JSONDumps, RPCOperation

from .rpc_request import RPCRequest
from .rpc_request_options import RPCRequestOptions

_DEFAULT_HEADERS = (
    ("Content-Type", "application/json"),
    ("Accept", "application/json"),
)


class RPCRequestBuilder:
    """Build an immutable HTTP-ready request from a typed method instance."""

    def __init__(
        self,
        *,
        api_server: APIServer,
        json_dumps: JSONDumps,
    ) -> None:
        self.api_server = api_server
        self.json_dumps = json_dumps
        self._operation_adapter: TypeAdapter[RPCOperation] = TypeAdapter(RPCOperation)
        self._http_method_adapter: TypeAdapter[HTTPMethod] = TypeAdapter(HTTPMethod)

    def build[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        options: RPCRequestOptions | None = None,
    ) -> RPCRequest:
        operation = self._parse_operation(method)
        http_method = self._parse_http_method(method)

        dumped = method.model_dump(mode="json", by_alias=False, exclude_unset=True)
        serialized = self.json_dumps(dumped)
        if not isinstance(serialized, str):
            raise TypeError("json_dumps must return str")

        request_options = options if options is not None else RPCRequestOptions()
        custom_header_names = {name.casefold() for name, _ in request_options.headers}
        headers = (
            tuple(
                (name, value)
                for name, value in _DEFAULT_HEADERS
                if name.casefold() not in custom_header_names
            )
            + request_options.headers
        )

        return RPCRequest(
            operation=operation,
            http_method=http_method,
            url=self.api_server.api_url(operation),
            content=serialized.encode("utf-8"),
            headers=headers,
        )

    def _parse_operation[ResultT](
        self,
        method: PokerlostMethod[ResultT],
    ) -> RPCOperation:
        try:
            return self._operation_adapter.validate_python(method.__api_method__)
        except (AttributeError, ValidationError):
            pass
        raise TypeError(
            "Concrete methods must declare a lowercase namespace.method __api_method__",
        ) from TypeError("RPC operation validation failed")

    def _parse_http_method[ResultT](
        self,
        method: PokerlostMethod[ResultT],
    ) -> HTTPMethod:
        try:
            return self._http_method_adapter.validate_python(
                method.__http_method__,
            )
        except (AttributeError, ValidationError):
            pass
        raise TypeError(
            "Concrete methods must declare __http_method__ as GET, POST, PUT, PATCH, or DELETE",
        ) from TypeError("HTTP method validation failed")
