from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from contextvars import Token
from types import TracebackType
from typing import Self

from pypokerlost.client import Client
from pypokerlost.client.context import reset_current_client, set_current_client
from pypokerlost.exceptions import ApplicationStateError


class Application:
    """Own the client lifecycle and task-local execution scope."""

    def __init__(self, client: Client) -> None:
        self._client = client
        self._is_running = False
        self._context_token: Token[Client | None] | None = None

    @property
    def client(self) -> Client:
        return self._client

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def __aenter__(self) -> Self:
        if self._is_running:
            raise ApplicationStateError
        self._is_running = True

        try:
            await self._client.start()
        except BaseException:
            self._is_running = False
            raise

        try:
            token = set_current_client(self._client)
        except BaseException:
            try:
                with suppress(BaseException):
                    await self._client.stop()
            finally:
                self._is_running = False
            raise

        self._context_token = token
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        token = self._context_token
        try:
            if exc_value is None:
                await self._client.stop()
            else:
                with suppress(BaseException):
                    await self._client.stop()
        finally:
            try:
                if token is not None:
                    reset_current_client(token)
            finally:
                self._context_token = None
                self._is_running = False

    async def run_async[ResultT](
        self,
        entrypoint: Callable[[Client], Awaitable[ResultT]],
    ) -> ResultT:
        async with self:
            return await entrypoint(self.client)

    def run[ResultT](
        self,
        entrypoint: Callable[[Client], Awaitable[ResultT]],
    ) -> ResultT:
        return asyncio.run(self.run_async(entrypoint))
