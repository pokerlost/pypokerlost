from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

import httpx

from pypokerlost.errors import TransportError
from pypokerlost.session.base_session import BaseSession
from pypokerlost.session.content_stream import ContentStream
from pypokerlost.session.prepared_request import PreparedRequest
from pypokerlost.session.raw_response import RawResponse


class HttpxSession(BaseSession):
    """Production session adapter backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float | None = 10.0,
        default_headers: Mapping[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        self._base_url = self._normalize_base_url(base_url)
        self._timeout = httpx.Timeout(timeout)
        self._default_headers = dict({} if default_headers is None else default_headers)
        self._client = (
            httpx.AsyncClient(timeout=self._timeout, trust_env=False) if client is None else client
        )
        self._closed = False

    @property
    def base_url(self) -> str:
        return str(self._base_url)

    @property
    def is_closed(self) -> bool:
        return self._closed

    async def _execute(self, request: PreparedRequest, *, operation: str) -> RawResponse:
        self._ensure_open()
        http_request = self._build_request(request)
        try:
            response = await self._client.send(http_request)
        except httpx.TransportError as error:
            raise self._mapped_error(error, operation=operation) from error

        return RawResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    async def _open_stream(self, request: PreparedRequest, *, operation: str) -> ContentStream:
        self._ensure_open()
        http_request = self._build_request(request)
        try:
            response = await self._client.send(http_request, stream=True)
        except httpx.TransportError as error:
            raise self._mapped_error(error, operation=operation) from error

        return ContentStream(
            status_code=response.status_code,
            headers=dict(response.headers),
            byte_iterator=self._iterate_response(response, operation=operation),
            close_callback=lambda: self._close_response(response, operation=operation),
        )

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        try:
            await self._client.aclose()
        except httpx.TransportError as error:
            raise self._mapped_error(error, operation=None) from error

    def _build_request(self, request: PreparedRequest) -> httpx.Request:
        headers = httpx.Headers(self._default_headers)
        headers.update(request.headers)
        request_url = self._join_path(request.path)
        json_body = request.json_body

        if json_body is None:
            return self._client.build_request(
                method=request.method,
                url=request_url,
                params=request.query,
                headers=headers,
                timeout=self._timeout,
            )
        return self._client.build_request(
            method=request.method,
            url=request_url,
            params=request.query,
            json=json_body,
            headers=headers,
            timeout=self._timeout,
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
            raise self._mapped_error(error, operation=operation) from error

    async def _close_response(self, response: httpx.Response, *, operation: str) -> None:
        try:
            await response.aclose()
        except httpx.TransportError as error:
            raise self._mapped_error(error, operation=operation) from error

    def _join_path(self, path: str) -> httpx.URL:
        base_path = self._base_url.path.rstrip("/")
        joined_path = f"{base_path}/{path.lstrip('/')}"
        return self._base_url.copy_with(path=joined_path)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("HTTP session is closed")

    @staticmethod
    def _mapped_error(error: httpx.TransportError, *, operation: str | None) -> TransportError:
        return TransportError(
            operation=operation,
            detail=f"HTTP transport failed with {error.__class__.__name__}",
        )

    @staticmethod
    def _normalize_base_url(base_url: str) -> httpx.URL:
        parsed_url = httpx.URL(base_url.strip())
        if parsed_url.scheme not in {"http", "https"} or parsed_url.host is None:
            raise ValueError("Base URL must be an absolute HTTP or HTTPS URL")
        if parsed_url.query or parsed_url.fragment:
            raise ValueError("Base URL must not contain a query string or fragment")

        normalized_path = parsed_url.path.rstrip("/") or "/"
        return parsed_url.copy_with(path=normalized_path)
