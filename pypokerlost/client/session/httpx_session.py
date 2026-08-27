from __future__ import annotations

import json
from contextlib import AsyncExitStack

import httpx

from pypokerlost.environment import PRODUCTION, APIServer
from pypokerlost.exceptions import ClientConnectionError, ClientTimeoutError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.request import RPCRequestBuilder
from pypokerlost.response import ApplicationResponseHandler
from pypokerlost.types import JSONDumps, JSONLoads

from .base_session import DEFAULT_TIMEOUT, BaseSession


class HttpxSession(BaseSession):
    """Restartable session that lazily owns one ``httpx.AsyncClient``."""

    def __init__(
        self,
        *,
        api_server: APIServer = PRODUCTION,
        json_dumps: JSONDumps = json.dumps,
        json_loads: JSONLoads = json.loads,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        request_builder = RPCRequestBuilder(
            api_server=api_server,
            json_dumps=json_dumps,
        )
        response_handler = ApplicationResponseHandler(json_loads=json_loads)
        super().__init__(
            request_builder=request_builder,
            response_handler=response_handler,
            timeout=timeout,
        )
        self._http_client: httpx.AsyncClient | None = None
        self._context_stack: AsyncExitStack | None = None

    async def start(self) -> None:
        if self._http_client is None:
            async with AsyncExitStack() as entry_stack:
                self._http_client = await entry_stack.enter_async_context(
                    httpx.AsyncClient(),
                )
                self._context_stack = entry_stack.pop_all()

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        timeout: int,
    ) -> ResultT:
        request = self.request_builder.build(method)
        await self.start()
        http_client = self._http_client
        if http_client is None:
            raise RuntimeError("HttpxSession failed to start")

        try:
            response = await http_client.request(
                method=request.http_method,
                url=request.url,
                content=request.content,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=timeout,
            )
        except httpx.TimeoutException as error:
            raise ClientTimeoutError(
                method=method,
                operation=request.operation,
            ) from error
        except httpx.TransportError as error:
            raise ClientConnectionError(
                method=method,
                operation=request.operation,
            ) from error

        return self.response_handler.handle(
            method=method,
            operation=request.operation,
            status_code=response.status_code,
            content=response.text,
        )

    async def close(self) -> None:
        context_stack = self._context_stack
        self._context_stack = None
        if context_stack is None:
            self._http_client = None
            return

        async with context_stack:
            self._http_client = None
