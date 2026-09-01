"""Central asynchronous PokerLost API client."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Self, cast

from pypokerlost.client.current_client import use_current_client
from pypokerlost.client.request import RequestOptions
from pypokerlost.client.retry import PokerLostRetryPolicy
from pypokerlost.client.retry.executor import execute_with_retry
from pypokerlost.client.session import BaseSession, HttpxSession
from pypokerlost.exceptions import ClientRequestError, ClientStateError, ClientTimeoutError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.storage import BaseStorage, MemoryStorage
from pypokerlost.types import APIOperation, HTTPMethod, HTTPRequestContentType


class Client:
    """Own one pluggable asynchronous session and storage resource."""

    def __init__(
        self,
        session: BaseSession | None = None,
        storage: BaseStorage | None = None,
    ) -> None:
        self.session: BaseSession = session if session is not None else HttpxSession()
        self.storage: BaseStorage = storage if storage is not None else MemoryStorage()
        self._context_stack: AsyncExitStack | None = None

    async def start(self) -> Self:
        async with AsyncExitStack() as rollback_stack:
            await self.storage.start()
            rollback_stack.push_async_callback(self.storage.close)
            await self.session.start()
            rollback_stack.push_async_callback(self.session.close)
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
        content_type = cast("HTTPRequestContentType", None)
        transport_options = RequestOptions()
        retry_policy: PokerLostRetryPolicy | None = None
        budget_timeout_error: ClientTimeoutError | None = None
        execute_session = cast("Callable[[], Awaitable[ResultT]]", None)
        returning: object = None
        setup_failure: ClientRequestError | None = None
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
                operation, http_method, content_type = self.session.request_builder.describe(
                    executing_method
                )
                returning = executing_method.__returning__
            except Exception:
                setup_failure = ClientRequestError(
                    method=method,
                    operation=operation,
                )

            if setup_failure is None:
                retry_policy = request_options.retry
                transport_options = request_options.model_copy(update={"retry": None})

                async def execute_session() -> ResultT:
                    return await self.session._make_request_with_metadata(
                        executing_method,
                        operation=operation,
                        http_method=http_method,
                        content_type=content_type,
                        returning=returning,
                        timeout=request_timeout,
                        options=transport_options,
                    )

                if retry_policy is None:
                    return await execute_session()
                budget_timeout_error = ClientTimeoutError(
                    method=executing_method,
                    operation=operation,
                )
                return await execute_with_retry(
                    execute_session,
                    retry_policy,
                    budget_timeout_error,
                )
        finally:
            method = None  # type: ignore[assignment]
            executing_method = None  # type: ignore[assignment]
            options = None
            request_options = RequestOptions()
            transport_options = RequestOptions()
            retry_policy = None
            budget_timeout_error = None
            execute_session = cast("Callable[[], Awaitable[ResultT]]", None)
            returning = None

        if setup_failure is None:
            raise AssertionError("Client request setup completed without a result")
        raise setup_failure from None

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
