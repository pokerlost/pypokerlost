from __future__ import annotations

from contextlib import AsyncExitStack
from types import TracebackType
from typing import Self

from pypokerlost.client.current_client import use_current_client
from pypokerlost.client.session import BaseSession, HttpxSession
from pypokerlost.exceptions import ClientStateError
from pypokerlost.methods import PokerlostMethod


class Client:
    """Thin facade over one pluggable asynchronous session."""

    def __init__(self, session: BaseSession | None = None) -> None:
        self.session = session if session is not None else HttpxSession()
        self._context_stack: AsyncExitStack | None = None

    async def start(self) -> Self:
        await self.session.start()
        return self

    async def stop(self) -> None:
        await self.session.close()

    async def __call__[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        request_timeout: int | None = None,
    ) -> ResultT:
        executing_method = method.model_copy().as_(self)
        return await self.session(executing_method, timeout=request_timeout)

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        request_timeout: int | None = None,
    ) -> ResultT:
        return await self(method, request_timeout=request_timeout)

    async def __aenter__(self) -> Self:
        if self._context_stack is not None:
            raise ClientStateError

        context_stack = AsyncExitStack()
        self._context_stack = context_stack
        await context_stack.__aenter__()
        context_stack.push_async_callback(self.stop)

        try:
            await self.start()
            context_stack.enter_context(use_current_client(self))
        except BaseException:
            try:
                await context_stack.aclose()
            finally:
                self._context_stack = None
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        context_stack = self._context_stack
        if context_stack is None:
            return
        try:
            await context_stack.__aexit__(exc_type, exc_value, traceback)
        finally:
            self._context_stack = None
