"""Central asynchronous PokerLost API client."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Self, cast

from pypokerlost.client.current_client import use_current_client
from pypokerlost.client.request import RequestOptions
from pypokerlost.client.session import BaseSession, HttpxSession
from pypokerlost.exceptions import ClientStateError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.middleware import BaseMiddleware, MiddlewareHandler
from pypokerlost.storage import BaseStorage, MemoryStorage


class Client:
    """Own one pluggable asynchronous session and storage resource."""

    def __init__(
        self,
        session: BaseSession | None = None,
        storage: BaseStorage | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
    ) -> None:
        self.session: BaseSession = session if session is not None else HttpxSession()
        self.storage: BaseStorage = storage if storage is not None else MemoryStorage()
        self._middleware: list[BaseMiddleware] = list(middleware) if middleware is not None else []
        self._context_stack: AsyncExitStack | None = None

    @property
    def middleware(self) -> tuple[BaseMiddleware, ...]:
        """Return an immutable snapshot of configured middleware."""
        return tuple(self._middleware)

    def add_middleware(self, middleware: BaseMiddleware) -> Self:
        """Append one middleware component for subsequent requests."""
        self._middleware.append(middleware)
        return self

    async def start(self) -> Self:
        await self.storage.start()
        async with AsyncExitStack() as rollback_stack:
            rollback_stack.push_async_callback(self.storage.close)
            await self.session.start()
            rollback_stack.pop_all()
        return self

    async def stop(self) -> None:
        async with AsyncExitStack() as cleanup_stack:
            cleanup_stack.push_async_callback(self.storage.close)
            cleanup_stack.push_async_callback(self.session.close)

    async def __call__[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        request_timeout: int | None = None,
    ) -> ResultT:
        return await self.make_request(method, request_timeout=request_timeout)

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        request_timeout: int | None = None,
    ) -> ResultT:
        executing_method = method.model_copy().as_(self)
        middleware = tuple(self._middleware)
        if not middleware:
            return await self.session(
                executing_method,
                timeout=request_timeout,
                options=RequestOptions(),
            )

        async def session_handler[NextResultT](
            next_method: PokerlostMethod[NextResultT],
            *,
            options: RequestOptions | None = None,
        ) -> NextResultT:
            request_options = options if options is not None else RequestOptions()
            return await self.session(
                next_method,
                timeout=request_timeout,
                options=request_options,
            )

        handler = cast(MiddlewareHandler, session_handler)
        for component in reversed(middleware):
            handler = self._wrap_middleware(component, handler)
        return await handler(executing_method)

    def _wrap_middleware(
        self,
        middleware: BaseMiddleware,
        handler: MiddlewareHandler,
    ) -> MiddlewareHandler:
        async def wrapped_handler[ResultT](
            method: PokerlostMethod[ResultT],
            *,
            options: RequestOptions | None = None,
        ) -> ResultT:
            request_options = options if options is not None else RequestOptions()

            async def next_handler[NextResultT](
                next_method: PokerlostMethod[NextResultT],
                *,
                options: RequestOptions | None = None,
            ) -> NextResultT:
                next_options = options if options is not None else request_options
                executing_next_method = (
                    next_method if next_method is method else next_method.model_copy().as_(self)
                )
                return await handler(executing_next_method, options=next_options)

            return await middleware(
                cast(MiddlewareHandler, next_handler),
                method,
                self,
                request_options,
            )

        return wrapped_handler

    async def __aenter__(self) -> Self:
        if self._context_stack is not None:
            raise ClientStateError

        entry_stack = AsyncExitStack()
        self._context_stack = entry_stack
        try:
            async with entry_stack:
                await entry_stack.enter_async_context(self.storage)
                await entry_stack.enter_async_context(self.session)
                entry_stack.enter_context(use_current_client(self))
                self._context_stack = entry_stack.pop_all()
        except BaseException:
            self._context_stack = None
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        context_stack = self._context_stack
        if context_stack is None:
            return
        try:
            try:
                async with context_stack:
                    if exc_value is not None:
                        raise exc_value.with_traceback(traceback)
            except BaseException as propagated_error:
                if propagated_error is not exc_value:
                    raise
        finally:
            self._context_stack = None
