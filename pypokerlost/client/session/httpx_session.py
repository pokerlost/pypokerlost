"""httpx-backed asynchronous PokerLost transport session."""

from __future__ import annotations

import json

import httpx

from pypokerlost.client.api_server import PRODUCTION, APIServer
from pypokerlost.client.request import RequestBuilder, RequestOptions
from pypokerlost.client.response import ResponseHandler
from pypokerlost.exceptions import ClientConnectionError, ClientTimeoutError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import JSONDumps, JSONLoads, JSONValue

from .base_session import DEFAULT_TIMEOUT, BaseSession


def _strict_json_dumps(value: JSONValue) -> str:
    return json.dumps(value, allow_nan=False)


class HttpxSession(BaseSession):
    """Restartable session that lazily owns one ``httpx.AsyncClient``."""

    def __init__(
        self,
        *,
        api_server: APIServer = PRODUCTION,
        json_dumps: JSONDumps = _strict_json_dumps,
        json_loads: JSONLoads = json.loads,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        request_builder = RequestBuilder()
        response_handler = ResponseHandler(json_loads=json_loads)
        super().__init__(
            request_builder=request_builder,
            response_handler=response_handler,
            timeout=timeout,
        )
        self._api_server = api_server
        self._json_dumps = json_dumps
        self._http_client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        timeout: int,
        *,
        options: RequestOptions,
    ) -> ResultT:
        request = self.request_builder.build(method, options=options)
        url = self._api_server.api_url(request.method)
        serialized = self._json_dumps(request.data)
        if not isinstance(serialized, str):
            raise TypeError("json_dumps must return str")
        content = serialized.encode("utf-8")

        await self.start()
        http_client = self._http_client
        if http_client is None:
            raise RuntimeError("HttpxSession failed to start")

        client_error: ClientTimeoutError | ClientConnectionError
        safe_cause: TimeoutError | ConnectionError
        try:
            response = await http_client.request(
                method=request.http_method,
                url=url,
                content=content,
                headers=request.headers,
                timeout=timeout,
            )
        except httpx.TimeoutException:
            client_error = ClientTimeoutError(
                method=method,
                operation=request.method,
            )
            safe_cause = TimeoutError("HTTP request timed out")
        except httpx.TransportError:
            client_error = ClientConnectionError(
                method=method,
                operation=request.method,
            )
            safe_cause = ConnectionError("HTTP transport failed")
        else:
            return self.response_handler.handle(
                method=method,
                operation=request.method,
                status_code=response.status_code,
                content=response.text,
            )

        raise client_error from safe_cause

    async def close(self) -> None:
        http_client = self._http_client
        self._http_client = None
        if http_client is not None:
            await http_client.aclose()
