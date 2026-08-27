from __future__ import annotations

from pydantic import TypeAdapter, ValidationError

from pypokerlost.environment import APIServer
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import HTTPMethod, JSONDumps, RPCOperation

from .rpc_request import RPCRequest


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

    def build[ResultT](self, method: PokerlostMethod[ResultT]) -> RPCRequest:
        try:
            operation = self._operation_adapter.validate_python(method.__api_method__)
        except AttributeError:
            raise TypeError("Concrete methods must declare a non-empty __api_method__") from None
        except ValidationError as error:
            raise TypeError(
                "Concrete methods must declare a non-empty __api_method__",
            ) from error

        try:
            http_method = self._http_method_adapter.validate_python(
                method.__http_method__,
            )
        except AttributeError:
            raise TypeError("Concrete methods must declare a non-empty __http_method__") from None
        except ValidationError as error:
            raise TypeError(
                "Concrete methods must declare a non-empty __http_method__",
            ) from error

        dumped = method.model_dump(mode="json", by_alias=False, exclude_unset=True)
        serialized = self.json_dumps(dumped)
        if not isinstance(serialized, str):
            raise TypeError("json_dumps must return str")

        return RPCRequest(
            operation=operation,
            http_method=http_method,
            url=self.api_server.api_url(operation),
            content=serialized.encode("utf-8"),
        )
