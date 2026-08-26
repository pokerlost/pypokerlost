from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractAsyncContextManager, contextmanager
from typing import Self

from pypokerlost.client.context import reset_current_client, set_current_client
from pypokerlost.client.session import BaseSession, ContentStream
from pypokerlost.methods import Method, StreamMethod


class Client:
    """Facade for typed methods, current-client context, and session delegation."""

    def __init__(self, session: BaseSession) -> None:
        self.session = session

    async def make_request[ResultT](self, method: Method[ResultT]) -> ResultT:
        return await self.session.make_request(self, method)

    async def __call__[ResultT](self, method: Method[ResultT]) -> ResultT:
        return await self.make_request(method)

    def stream_content(self, method: StreamMethod) -> AbstractAsyncContextManager[ContentStream]:
        return self.session.stream_content(self, method)

    @contextmanager
    def as_current(self) -> Iterator[Self]:
        token = set_current_client(self)
        try:
            yield self
        finally:
            reset_current_client(token)

    async def close(self) -> None:
        await self.session.close()
