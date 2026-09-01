"""Central asynchronous PokerLost API client."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Self, cast

from pypokerlost.client.current_client import use_current_client
from pypokerlost.client.request import RequestOptions
from pypokerlost.client.session import BaseSession, HttpxSession
from pypokerlost.exceptions import ClientRequestError, ClientStateError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.middleware import (
    APIMiddleware,
    APIMiddlewareCallNext,
    APIMiddlewareContext,
)
from pypokerlost.storage import BaseStorage, MemoryStorage
from pypokerlost.types import APIOperation, HTTPMethod


class Client:
    """Own one pluggable asynchronous session and storage resource."""

    def __init__(
        self,
        session: BaseSession | None = None,
        storage: BaseStorage | None = None,
        middleware: Sequence[APIMiddleware] | None = None,
    ) -> None:
        self.session: BaseSession = session if session is not None else HttpxSession()
        self.storage: BaseStorage = storage if storage is not None else MemoryStorage()
        self._middleware: tuple[APIMiddleware, ...] = (
            tuple(middleware) if middleware is not None else ()
        )
        self._context_stack: AsyncExitStack | None = None

    @property
    def middleware(self) -> tuple[APIMiddleware, ...]:
        """Return the immutable configured middleware tuple."""
        return self._middleware

    async def start(self) -> Self:
        async with AsyncExitStack() as rollback_stack:
            await self.storage.start()
            rollback_stack.push_async_callback(self.storage.close)
            await self.session.start()
            rollback_stack.push_async_callback(self.session.close)
            for component in self._middleware:
                await component.start()
                rollback_stack.push_async_callback(component.close)
            rollback_stack.pop_all()
        return self

    async def stop(self) -> None:
        async with AsyncExitStack() as cleanup_stack:
            cleanup_stack.push_async_callback(self.storage.close)
            cleanup_stack.push_async_callback(self.session.close)
            for component in self._middleware:
                cleanup_stack.push_async_callback(component.close)

    async def __call__[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        request_timeout: int | None = None,
        *,
        options: RequestOptions | None = None,
    ) -> ResultT:
        try:
            return await self.make_request(
                method,
                request_timeout=request_timeout,
                options=options,
            )
        finally:
            method = None  # type: ignore[assignment]
            options = None

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        request_timeout: int | None = None,
        *,
        options: RequestOptions | None = None,
    ) -> ResultT:
        executing_method = cast("PokerlostMethod[ResultT]", None)
        request_options = RequestOptions()
        operation = cast("APIOperation", None)
        http_method = cast("HTTPMethod", None)
        returning: object = None
        setup_failure: ClientRequestError | None = None
        handler = cast("APIMiddlewareCallNext[ResultT]", None)
        component: APIMiddleware | None = None
        try:
            try:
                executing_method = (
                    type(method)
                    .model_validate(
                        method.model_dump(
                            mode="python",
                            by_alias=False,
                            exclude_unset=True,
                        ),
                    )
                    .as_(self)
                )
                request_options = options if options is not None else RequestOptions()
                operation, http_method = self.session.request_builder.describe(executing_method)
                returning = executing_method.__returning__
            except Exception:
                setup_failure = ClientRequestError(
                    method=method,
                    operation=operation,
                )

            if setup_failure is None:

                async def execute_session(
                    execution_options: RequestOptions,
                ) -> ResultT:
                    try:
                        return await self.session._make_request_with_metadata(
                            executing_method,
                            operation=operation,
                            http_method=http_method,
                            returning=returning,
                            timeout=request_timeout,
                            options=execution_options,
                        )
                    finally:
                        execution_options = RequestOptions()

                if not self._middleware:
                    return await execute_session(request_options)

                async def session_handler(
                    *,
                    options: RequestOptions | None = None,
                ) -> ResultT:
                    next_options = options if options is not None else request_options
                    try:
                        return await execute_session(next_options)
                    finally:
                        options = None
                        next_options = RequestOptions()

                handler = session_handler
                for component in reversed(self._middleware):
                    handler = self._wrap_middleware(
                        component,
                        handler,
                        operation=operation,
                        http_method=http_method,
                    )
                return await handler(options=request_options)
        finally:
            method = None  # type: ignore[assignment]
            executing_method = None  # type: ignore[assignment]
            options = None
            request_options = RequestOptions()
            returning = None
            handler = cast("APIMiddlewareCallNext[ResultT]", None)
            component = None

        if setup_failure is None:
            raise AssertionError("Client request setup completed without a result")
        raise setup_failure from None

    def _wrap_middleware[ResultT](
        self,
        middleware: APIMiddleware,
        call_next: APIMiddlewareCallNext[ResultT],
        *,
        operation: APIOperation,
        http_method: HTTPMethod,
    ) -> APIMiddlewareCallNext[ResultT]:
        async def wrapped_handler(
            *,
            options: RequestOptions | None = None,
        ) -> ResultT:
            request_options = options if options is not None else RequestOptions()
            context = APIMiddlewareContext(
                operation=operation,
                http_method=http_method,
                options=request_options,
            )

            async def next_handler(
                *,
                options: RequestOptions | None = None,
            ) -> ResultT:
                next_options = options if options is not None else request_options
                try:
                    return await call_next(options=next_options)
                finally:
                    options = None
                    next_options = RequestOptions()

            try:
                return await middleware(
                    next_handler,
                    context,
                )
            finally:
                options = None
                request_options = RequestOptions()
                context = None  # type: ignore[assignment]

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
                for component in self._middleware:
                    await entry_stack.enter_async_context(component)
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
