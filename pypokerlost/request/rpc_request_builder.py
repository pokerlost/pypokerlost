from __future__ import annotations

from pypokerlost.enums import ServiceName
from pypokerlost.environment import APIServer
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import JSONDumps

from .request_value_preparer import RequestValuePreparer
from .rpc_request import RpcRequest


class RpcRequestBuilder:
    """Build an immutable HTTP-ready request from a typed method instance."""

    def __init__(
        self,
        *,
        api_server: APIServer,
        json_dumps: JSONDumps,
        value_preparer: RequestValuePreparer | None = None,
    ) -> None:
        self.api_server = api_server
        self.json_dumps = json_dumps
        self.value_preparer = (
            value_preparer if value_preparer is not None else RequestValuePreparer()
        )

    def build[ResultT](self, method: PokerlostMethod[ResultT]) -> RpcRequest:
        try:
            service = method.__service__
        except AttributeError:
            raise TypeError("Concrete methods must declare __service__ as ServiceName") from None
        if not isinstance(service, ServiceName):
            raise TypeError("Concrete methods must declare __service__ as ServiceName")

        try:
            operation = method.__api_method__
        except AttributeError:
            raise TypeError("Concrete methods must declare a non-empty __api_method__") from None
        if not isinstance(operation, str) or not operation.strip():
            raise TypeError("Concrete methods must declare a non-empty __api_method__")

        try:
            http_method = method.__http_method__
        except AttributeError:
            raise TypeError("Concrete methods must declare a non-empty __http_method__") from None
        if not isinstance(http_method, str) or not http_method.strip():
            raise TypeError("Concrete methods must declare a non-empty __http_method__")

        dumped = method.model_dump(mode="json", by_alias=False, exclude_unset=True)
        prepared = self.value_preparer.prepare_value(dumped)
        serialized = self.json_dumps(prepared)
        if not isinstance(serialized, str):
            raise TypeError("json_dumps must return str")

        return RpcRequest(
            service=service,
            operation=operation,
            http_method=http_method,
            url=self.api_server.api_url(operation),
            content=serialized.encode("utf-8"),
        )
