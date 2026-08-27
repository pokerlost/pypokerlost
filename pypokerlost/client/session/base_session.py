from __future__ import annotations

import abc
from types import TracebackType
from typing import Self

from pypokerlost.methods import PokerlostMethod
from pypokerlost.request import RPCRequestBuilder
from pypokerlost.response import BaseResponseHandler

DEFAULT_TIMEOUT = 10


class BaseSession(abc.ABC):
    """Orchestrate request building, execution, and response handling."""

    def __init__(
        self,
        *,
        request_builder: RPCRequestBuilder,
        response_handler: BaseResponseHandler,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._request_builder = request_builder
        self._response_handler = response_handler
        self._timeout = timeout

    @property
    def request_builder(self) -> RPCRequestBuilder:
        return self._request_builder

    @property
    def response_handler(self) -> BaseResponseHandler:
        return self._response_handler

    @property
    def timeout(self) -> int:
        return self._timeout

    async def start(self) -> None:  # noqa: B027
        """Start session resources; the default implementation has none."""

    async def __call__[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        timeout: int | None = None,
    ) -> ResultT:
        effective_timeout = self.timeout if timeout is None else timeout
        return await self.make_request(method, timeout=effective_timeout)

    @abc.abstractmethod
    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        timeout: int,
    ) -> ResultT:
        """Send one method and return its declared result."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Close resources held by the session."""

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
