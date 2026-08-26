from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from types import TracebackType

from pypokerlost.client import Client
from pypokerlost.exceptions import ApplicationStateError


class Application:
    """Coordinate automatic lifecycle for one client."""

    def __init__(self, client: Client) -> None:
        self._client = client
        self._is_running = False

    @property
    def client(self) -> Client:
        return self._client

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def __aenter__(self) -> Client:
        if self._is_running:
            raise ApplicationStateError
        self._is_running = True

        try:
            await self._client.start()
        except BaseException:
            self._is_running = False
            raise
        return self._client

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            await self._client.stop()
        finally:
            self._is_running = False

    async def run_async[ResultT](
        self,
        entrypoint: Callable[[Client], Awaitable[ResultT]],
    ) -> ResultT:
        async with self as client:
            return await entrypoint(client)

    def run[ResultT](
        self,
        entrypoint: Callable[[Client], Awaitable[ResultT]],
    ) -> ResultT:
        return asyncio.run(self.run_async(entrypoint))
