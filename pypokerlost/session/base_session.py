from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, final

from pypokerlost.request import RequestBuilder
from pypokerlost.response import ResponseHandler
from pypokerlost.session.content_stream import ContentStream
from pypokerlost.session.prepared_request import PreparedRequest
from pypokerlost.session.raw_response import RawResponse

if TYPE_CHECKING:
    from pypokerlost.methods import Method, StreamMethod


class BaseSession(ABC):
    """Shared request/response algorithm around a concrete I/O adapter."""

    def __init__(self) -> None:
        self._request_builder = RequestBuilder()
        self._response_handler = ResponseHandler()

    @final
    async def make_request[ResultT](self, method: Method[ResultT]) -> ResultT:
        request = self._request_builder.build(method)
        response = await self._execute(request, operation=method.operation)
        return self._response_handler.handle(method, response)

    @final
    @asynccontextmanager
    async def stream_content(self, method: StreamMethod) -> AsyncIterator[ContentStream]:
        request = self._request_builder.build(method)
        content = await self._open_stream(request, operation=method.operation)
        try:
            await self._response_handler.validate_stream_response(method, content)
            yield content
        finally:
            await content.aclose()

    @abstractmethod
    async def _execute(self, request: PreparedRequest, *, operation: str) -> RawResponse:
        """Execute and fully read an ordinary prepared request."""

    @abstractmethod
    async def _open_stream(self, request: PreparedRequest, *, operation: str) -> ContentStream:
        """Open a live prepared response without buffering its content."""

    @abstractmethod
    async def close(self) -> None:
        """Release session resources. Repeated calls must be safe."""
