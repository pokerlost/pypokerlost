"""Central asynchronous body-only Pokerlost client."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Self, cast

from pydantic import ValidationError

from pypokerlost.errors import PokerlostConfigurationError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.middleware import (
    PokerlostAuthorizationMiddleware,
    PokerlostCallNext,
    PokerlostMiddleware,
    PokerlostMiddlewareRequest,
    PokerlostRetryMiddleware,
)
from pypokerlost.session import HttpxSession, PokerlostSession

from .pokerlost_request_builder import PokerlostRequestBuilder
from .pokerlost_request_options import PokerlostRequestOptions


class PokerlostClient:
    """Execute typed methods through retry, authorization, and JSON transport."""

    def __init__(
        self,
        session: PokerlostSession | None = None,
        *,
        middleware: Sequence[PokerlostMiddleware] = (),
    ) -> None:
        supplied = tuple(middleware)
        retry_count = sum(isinstance(item, PokerlostRetryMiddleware) for item in supplied)
        authorization_count = sum(
            isinstance(item, PokerlostAuthorizationMiddleware) for item in supplied
        )
        if retry_count > 1 or authorization_count > 1:
            raise PokerlostConfigurationError(
                "Pokerlost middleware can contain at most one retry and authorization layer"
            )
        if retry_count == 0:
            supplied = (PokerlostRetryMiddleware(), *supplied)
        retry_index = next(
            index
            for index, item in enumerate(supplied)
            if isinstance(item, PokerlostRetryMiddleware)
        )
        authorization_indexes = tuple(
            index
            for index, item in enumerate(supplied)
            if isinstance(item, PokerlostAuthorizationMiddleware)
        )
        if retry_index != 0 or (authorization_indexes and authorization_indexes[0] <= retry_index):
            raise PokerlostConfigurationError(
                "Middleware order must be retry outermost and authorization inside it"
            )
        self._session = session if session is not None else HttpxSession()
        self._middleware = supplied
        self._request_builder = PokerlostRequestBuilder()
        self._context_stack: AsyncExitStack | None = None

    @property
    def session(self) -> PokerlostSession:
        return self._session

    @property
    def middleware(self) -> tuple[PokerlostMiddleware, ...]:
        return self._middleware

    @property
    def has_authorization_middleware(self) -> bool:
        return any(isinstance(item, PokerlostAuthorizationMiddleware) for item in self._middleware)

    async def start(self) -> Self:
        await self._session.start()
        return self

    async def stop(self) -> None:
        await self._session.close()

    async def __call__[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        options: PokerlostRequestOptions | None = None,
    ) -> ResultT:
        try:
            return await self.make_request(
                method,
                options=options,
            )
        finally:
            self = cast("PokerlostClient", None)
            method = cast("PokerlostMethod[ResultT]", None)
            options = None

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        options: PokerlostRequestOptions | None = None,
    ) -> ResultT:
        executing_method = cast("PokerlostMethod[ResultT]", None)
        request = cast("PokerlostMiddlewareRequest", None)
        call_next = cast("PokerlostCallNext[object]", None)
        transport = cast("PokerlostCallNext[object]", None)
        layer = cast("PokerlostMiddleware", None)
        serialized_method = ""
        try:
            try:
                if not isinstance(method, PokerlostMethod):
                    raise TypeError("Pokerlost client requires a PokerlostMethod")
                serialized_method = method.model_dump_json(
                    by_alias=False,
                    exclude_unset=True,
                )
                executing_method = (
                    type(method)
                    .model_validate_json(
                        serialized_method,
                        strict=True,
                    )
                    .as_(self)
                )
                call_options = options if options is not None else PokerlostRequestOptions()
                request = cast(
                    "PokerlostMiddlewareRequest",
                    self._request_builder.build(executing_method, call_options),
                )
                if executing_method.required_scopes and not self.has_authorization_middleware:
                    raise PokerlostConfigurationError(
                        "Protected operation requires PokerlostAuthorizationMiddleware",
                        operation=executing_method.operation,
                    )
            except TypeError, ValueError, ValidationError:
                raise PokerlostConfigurationError(
                    "Pokerlost method could not be prepared"
                ) from None

            async def transport(
                current_request: PokerlostMiddlewareRequest,
                session: PokerlostSession = self._session,
            ) -> object:
                try:
                    return await session.send(current_request)
                finally:
                    current_request = cast("PokerlostMiddlewareRequest", None)
                    session = cast("PokerlostSession", None)

            call_next = transport
            for layer in reversed(self._middleware):
                call_next = self._wrap(layer, call_next)
            return cast(ResultT, await call_next(request))
        finally:
            self = cast("PokerlostClient", None)
            method = cast("PokerlostMethod[ResultT]", None)
            executing_method = cast("PokerlostMethod[ResultT]", None)
            options = None
            request = cast("PokerlostMiddlewareRequest", None)
            call_next = cast("PokerlostCallNext[object]", None)
            transport = cast("PokerlostCallNext[object]", None)
            layer = cast("PokerlostMiddleware", None)
            serialized_method = ""

    def _wrap(
        self,
        middleware: PokerlostMiddleware,
        call_next: PokerlostCallNext[object],
    ) -> PokerlostCallNext[object]:
        async def wrapped(
            request: PokerlostMiddlewareRequest,
            current_middleware: PokerlostMiddleware = middleware,
            current_call_next: PokerlostCallNext[object] = call_next,
        ) -> object:
            try:
                return await current_middleware(request, current_call_next)
            finally:
                request = cast("PokerlostMiddlewareRequest", None)
                current_middleware = cast("PokerlostMiddleware", None)
                current_call_next = cast("PokerlostCallNext[object]", None)

        return wrapped

    async def __aenter__(self) -> Self:
        if self._context_stack is not None:
            raise PokerlostConfigurationError("PokerlostClient context is already active")
        from .current_client import use_current_client

        stack = AsyncExitStack()
        self._context_stack = stack
        try:
            async with stack:
                await stack.enter_async_context(self._session)
                stack.enter_context(use_current_client(self))
                self._context_stack = stack.pop_all()
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
        stack = self._context_stack
        self._context_stack = None
        if stack is not None:
            await stack.aclose()
