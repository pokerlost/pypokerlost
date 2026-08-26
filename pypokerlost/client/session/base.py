from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from pypokerlost.methods import Method, StreamMethod

from .request import PreparedRequest, RequestBuilder
from .response import RawResponse, ResponseHandler
from .stream import ContentStream

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class BaseSession(ABC):
    """Shared request/response flow around a concrete session adapter."""

    def __init__(self) -> None:
        self.request_builder = RequestBuilder()
        self.response_handler = ResponseHandler()

    async def make_request[ResultT](
        self,
        client: Client,
        method: Method[ResultT],
    ) -> ResultT:
        request = self.request_builder.build(client, method)
        response = await self.execute(client, request)
        return self.response_handler.handle(client, method, response)

    @asynccontextmanager
    async def stream_content(
        self,
        client: Client,
        method: StreamMethod,
    ) -> AsyncIterator[ContentStream]:
        request = self.request_builder.build(client, method)
        content = await self.open_stream(client, request)
        try:
            yield content
        finally:
            await content.aclose()

    @abstractmethod
    async def execute(self, client: Client, request: PreparedRequest) -> RawResponse:
        """Send and fully buffer an ordinary response."""

    @abstractmethod
    async def open_stream(self, client: Client, request: PreparedRequest) -> ContentStream:
        """Open a response without buffering its content."""

    @abstractmethod
    async def close(self) -> None:
        """Close resources held by this session."""
