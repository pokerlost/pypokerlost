from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from pypokerlost.exceptions import TransportError

from .base import BaseSession
from .request import PreparedRequest
from .response import RawResponse
from .stream import ContentStream


class HttpxSession(BaseSession):
    """Thin session adapter over a caller-configured ``httpx.AsyncClient``."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        super().__init__()
        self.http_client = http_client

    async def execute(self, request: PreparedRequest) -> RawResponse:
        try:
            response = await self.http_client.send(self._build_request(request))
        except httpx.TransportError as error:
            raise TransportError(operation=request.operation) from error

        return RawResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    async def open_stream(self, request: PreparedRequest) -> ContentStream:
        try:
            response = await self.http_client.send(self._build_request(request), stream=True)
        except httpx.TransportError as error:
            raise TransportError(operation=request.operation) from error

        return ContentStream(
            status_code=response.status_code,
            headers=dict(response.headers),
            byte_iterator=self._iterate_response(response, operation=request.operation),
            close_callback=lambda: self._close_response(response, operation=request.operation),
        )

    async def close(self) -> None:
        try:
            await self.http_client.aclose()
        except httpx.TransportError as error:
            raise TransportError from error

    def _build_request(self, request: PreparedRequest) -> httpx.Request:
        return self.http_client.build_request(
            method=request.http_method,
            url=request.path,
            content=request.content,
            headers={"Content-Type": "application/json"},
        )

    async def _iterate_response(
        self,
        response: httpx.Response,
        *,
        operation: str,
    ) -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        except httpx.TransportError as error:
            raise TransportError(operation=operation) from error

    async def _close_response(self, response: httpx.Response, *, operation: str) -> None:
        try:
            await response.aclose()
        except httpx.TransportError as error:
            raise TransportError(operation=operation) from error
