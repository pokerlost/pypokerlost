from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pypokerlost.methods import Method, StreamMethod

from .request import PreparedRequest, RequestBuilder
from .response import RawResponse, ResponseHandler
from .stream import ContentStream


class BaseSession(ABC):
    """Shared request/response flow around a concrete session adapter."""

    def __init__(self) -> None:
        self.request_builder = RequestBuilder()
        self.response_handler = ResponseHandler()

    async def start(self) -> None:
        """Prepare the session; HTTP adapters normally need no eager work."""
        return None

    async def make_request[ResultT](self, method: Method[ResultT]) -> ResultT:
        request = self.request_builder.build(method)
        response = await self.execute(request)
        return self.response_handler.handle(method, request.operation, response)

    @asynccontextmanager
    async def stream_content(self, method: StreamMethod) -> AsyncIterator[ContentStream]:
        request = self.request_builder.build(method)
        content = await self.open_stream(request)
        try:
            yield content
        finally:
            await content.aclose()

    @abstractmethod
    async def execute(self, request: PreparedRequest) -> RawResponse:
        """Send and fully buffer an ordinary response."""

    @abstractmethod
    async def open_stream(self, request: PreparedRequest) -> ContentStream:
        """Open a response without buffering its content."""

    @abstractmethod
    async def close(self) -> None:
        """Close resources held by this session."""
