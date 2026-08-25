from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import AbstractAsyncContextManager, contextmanager
from contextvars import ContextVar, Token
from types import TracebackType
from typing import Literal, Self, overload

from pypokerlost.client.current_client import install_current_client, reset_current_client
from pypokerlost.errors import ClientClosedError
from pypokerlost.methods import Method, StreamMethod
from pypokerlost.session import BaseSession, ContentStream, HttpxSession

_DEFAULT_TIMEOUT = 10.0


class _TimeoutNotProvided:
    __slots__ = ()


_TIMEOUT_NOT_PROVIDED = _TimeoutNotProvided()


class Client:
    """Public facade for typed methods, context, and session lifecycle."""

    @overload
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float | None = _DEFAULT_TIMEOUT,
        default_headers: Mapping[str, str] | None = None,
        session: None = None,
        owns_session: Literal[True] | None = None,
    ) -> None: ...

    @overload
    def __init__(
        self,
        base_url: None = None,
        *,
        session: BaseSession,
        owns_session: bool | None = None,
    ) -> None: ...

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float | _TimeoutNotProvided | None = _TIMEOUT_NOT_PROVIDED,
        default_headers: Mapping[str, str] | None = None,
        session: BaseSession | None = None,
        owns_session: bool | None = None,
    ) -> None:
        resolved_session: BaseSession
        if session is None:
            if base_url is None:
                raise ValueError("base_url is required when session is not provided")
            if owns_session is False:
                raise ValueError("a client-created session must be owned by the client")
            resolved_timeout = (
                _DEFAULT_TIMEOUT if isinstance(timeout, _TimeoutNotProvided) else timeout
            )
            resolved_session = HttpxSession(
                base_url=base_url,
                timeout=resolved_timeout,
                default_headers=default_headers,
            )
            resolved_ownership = True
        else:
            if (
                base_url is not None
                or default_headers is not None
                or not isinstance(timeout, _TimeoutNotProvided)
            ):
                raise ValueError(
                    "base_url, timeout, and default_headers cannot be combined with session"
                )
            resolved_session = session
            resolved_ownership = owns_session is True

        self._session = resolved_session
        self._owns_session = resolved_ownership
        self._closed = False
        self._active_async_contexts = 0
        self._context_tokens: ContextVar[tuple[Token[Client | None], ...]] = ContextVar(
            f"pypokerlost_client_context_tokens_{id(self)}",
            default=(),
        )

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def owns_session(self) -> bool:
        return self._owns_session

    async def make_request[ResultT](self, method: Method[ResultT]) -> ResultT:
        self._ensure_open(method.operation)
        return await self._session.make_request(method)

    async def __call__[ResultT](self, method: Method[ResultT]) -> ResultT:
        return await self.make_request(method)

    def stream_content(self, method: StreamMethod) -> AbstractAsyncContextManager[ContentStream]:
        self._ensure_open(method.operation)
        return self._session.stream_content(method)

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
        if self._owns_session:
            await self._session.close()

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
            raise RuntimeError("Client context exited without a matching entry")
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
