from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import AbstractAsyncContextManager, contextmanager
from typing import Self

from pypokerlost.client.context import reset_current_client, set_current_client
from pypokerlost.client.session import BaseSession, ContentStream
from pypokerlost.exceptions import ClientClosedError, ClientNotStartedError
from pypokerlost.methods import Method, StreamMethod


class Client:
    """Lifecycle-aware facade over one owned session."""

    def __init__(self, session: BaseSession) -> None:
        self._session = session
        self._lifecycle_lock = asyncio.Lock()
        self._is_started = False
        self._is_closed = False

    @property
    def is_started(self) -> bool:
        return self._is_started

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    async def start(self) -> Self:
        async with self._lifecycle_lock:
            if self._is_closed:
                raise ClientClosedError
            if self._is_started:
                return self
            await self._session.start()
            self._is_started = True
            return self

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            if self._is_closed:
                return
            self._is_closed = True
            self._is_started = False
            await self._session.close()

    async def make_request[ResultT](self, method: Method[ResultT]) -> ResultT:
        self._require_started()
        return await self._session.make_request(method)

    async def __call__[ResultT](self, method: Method[ResultT]) -> ResultT:
        return await self.make_request(method)

    def stream_content(self, method: StreamMethod) -> AbstractAsyncContextManager[ContentStream]:
        self._require_started()
        return self._session.stream_content(method)

    @contextmanager
    def as_current(self) -> Iterator[Self]:
        token = set_current_client(self)
        try:
            yield self
        finally:
            reset_current_client(token)

    def _require_started(self) -> None:
        if self._is_closed:
            raise ClientClosedError
        if not self._is_started:
            raise ClientNotStartedError
