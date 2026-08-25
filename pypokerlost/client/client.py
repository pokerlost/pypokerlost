from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from types import TracebackType
from typing import TYPE_CHECKING, Self

from pypokerlost.client.current_client import (
    install_current_client,
    reset_current_client,
)
from pypokerlost.errors import (
    ClientClosedError,
    ResponseDecodeError,
    UnexpectedStatusError,
)
from pypokerlost.methods import Method, StreamMethod
from pypokerlost.transport import ContentStream, HttpxTransport, Transport

if TYPE_CHECKING:
    from pypokerlost.transport import TransportResponse


_ERROR_RESPONSE_LIMIT = 512


class Client:
    """Asynchronous SDK client that orchestrates typed method objects."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float | None = 10.0,
        default_headers: Mapping[str, str] | None = None,
        transport: Transport | None = None,
        owns_transport: bool | None = None,
    ) -> None:
        normalized_base_url = base_url.strip().rstrip("/")
        if not normalized_base_url:
            msg = "base_url must not be empty"
            raise ValueError(msg)
        if transport is None and owns_transport is False:
            msg = "a client-created transport must be owned by the client"
            raise ValueError(msg)

        self._base_url = normalized_base_url
        self._transport = (
            HttpxTransport(
                base_url=normalized_base_url,
                timeout=timeout,
                default_headers=default_headers,
            )
            if transport is None
            else transport
        )
        self._owns_transport = transport is None or owns_transport is True
        self._closed = False
        self._active_async_contexts = 0
        self._context_tokens: ContextVar[tuple[Token[Client | None], ...]] = ContextVar(
            f"pypokerlost_client_context_tokens_{id(self)}",
            default=(),
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def owns_transport(self) -> bool:
        return self._owns_transport

    async def make_request[ResultT](self, method: Method[ResultT]) -> ResultT:
        self._ensure_open(method.operation)
        request = method.build_request()
        response = await self._transport.execute(request, operation=method.operation)
        self._raise_for_status(response, operation=method.operation)

        try:
            return method.parse_response(response)
        except ResponseDecodeError as error:
            if error.operation is not None and error.status_code is not None:
                raise
            raise ResponseDecodeError(
                operation=error.operation or method.operation,
                status_code=(
                    error.status_code if error.status_code is not None else response.status_code
                ),
                detail=error.detail,
            ) from error

    async def __call__[ResultT](self, method: Method[ResultT]) -> ResultT:
        return await self.make_request(method)

    @asynccontextmanager
    async def stream_content(
        self,
        method: StreamMethod,
    ) -> AsyncIterator[ContentStream]:
        self._ensure_open(method.operation)
        request = method.build_request()
        content = await self._transport.open_stream(
            request,
            operation=method.operation,
        )
        try:
            if not self._is_success(content.status_code):
                response_body = await content.read_excerpt(_ERROR_RESPONSE_LIMIT + 1)
                raise UnexpectedStatusError(
                    content.status_code,
                    operation=method.operation,
                    response_body=response_body,
                )
            yield content
        finally:
            await content.aclose()

    @contextmanager
    def as_current(self) -> Iterator[Self]:
        self._ensure_open()
        token = install_current_client(self)
        try:
            yield self
        finally:
            reset_current_client(token)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_transport:
            await self._transport.close()

    async def __aenter__(self) -> Self:
        self._ensure_open()
        token = install_current_client(self)
        tokens = self._context_tokens.get()
        self._context_tokens.set((*tokens, token))
        self._active_async_contexts += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        tokens = self._context_tokens.get()
        if not tokens:
            msg = "Client context exited without a matching entry"
            raise RuntimeError(msg)
        token = tokens[-1]
        self._context_tokens.set(tokens[:-1])
        self._active_async_contexts -= 1
        try:
            if self._active_async_contexts == 0:
                await self.close()
        finally:
            reset_current_client(token)

    def _ensure_open(self, operation: str | None = None) -> None:
        if self._closed:
            raise ClientClosedError(operation=operation)

    @staticmethod
    def _is_success(status_code: int) -> bool:
        return 200 <= status_code < 300

    @classmethod
    def _raise_for_status(
        cls,
        response: TransportResponse,
        *,
        operation: str,
    ) -> None:
        if not cls._is_success(response.status_code):
            raise UnexpectedStatusError(
                response.status_code,
                operation=operation,
                response_body=response.body,
            )
