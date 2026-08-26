from __future__ import annotations

from types import TracebackType
from typing import Self

from pypokerlost.client.session import BaseSession, HttpxSession
from pypokerlost.methods import PokerlostMethod


class Client:
    """Thin facade over one pluggable asynchronous session."""

    def __init__(self, session: BaseSession | None = None) -> None:
        self.session = session if session is not None else HttpxSession()

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
        return await self.session(method.as_(self), timeout=request_timeout)

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        request_timeout: int | None = None,
    ) -> ResultT:
        return await self(method, request_timeout=request_timeout)

    async def __aenter__(self) -> Self:
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()
