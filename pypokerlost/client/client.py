"""Central asynchronous Pokerlost client."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AsyncExitStack, suppress
from types import TracebackType
from typing import Self, cast

from pypokerlost.enums import PokerlostScopes
from pypokerlost.errors import PokerlostConfigurationError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.middleware import (
    PokerlostAuthenticationMiddleware,
    PokerlostCallNext,
    PokerlostMiddleware,
    PokerlostRetryMiddleware,
)
from pypokerlost.middleware._call import PokerlostCall
from pypokerlost.session import HttpxSession, PokerlostSession
from pypokerlost.types import PokerlostRequest

from .pokerlost_api_server import PokerlostAPIServer
from .pokerlost_request_options import PokerlostRequestOptions

_MISSING = object()


class PokerlostClient:
    """Execute typed methods through authentication, retry, and JSON transport."""

    def __init__(
        self,
        session: PokerlostSession | None = None,
        *,
        server: PokerlostAPIServer | None = None,
        middleware: Sequence[PokerlostMiddleware] = (),
    ) -> None:
        if session is not None and server is not None:
            raise PokerlostConfigurationError("Pass either session or server, not both")
        supplied = tuple(middleware)
        retry_layers = tuple(
            item for item in supplied if isinstance(item, PokerlostRetryMiddleware)
        )
        authentication_layers = tuple(
            item for item in supplied if isinstance(item, PokerlostAuthenticationMiddleware)
        )
        if len(retry_layers) > 1 or len(authentication_layers) > 1:
            raise PokerlostConfigurationError(
                "Pokerlost middleware can contain at most one retry and authentication layer"
            )
        retry = retry_layers[0] if retry_layers else PokerlostRetryMiddleware()
        authentication = authentication_layers[0] if authentication_layers else None
        custom = tuple(
            item
            for item in supplied
            if not isinstance(item, PokerlostRetryMiddleware | PokerlostAuthenticationMiddleware)
        )
        # Retry owns the complete logical-call budget; authentication shares one refresh claim.
        self._middleware = (
            retry,
            *((authentication,) if authentication is not None else ()),
            *custom,
        )
        if session is not None:
            self._session = session
        elif server is not None:
            self._session = HttpxSession(api_server=server)
        else:
            self._session = HttpxSession()
        self._context_stack: AsyncExitStack | None = None

    @property
    def session(self) -> PokerlostSession:
        return self._session

    @property
    def middleware(self) -> tuple[PokerlostMiddleware, ...]:
        return self._middleware

    @property
    def has_authentication_middleware(self) -> bool:
        return any(isinstance(item, PokerlostAuthenticationMiddleware) for item in self._middleware)

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
        if not isinstance(method, PokerlostMethod):
            raise PokerlostConfigurationError("Pokerlost client requires a PokerlostMethod")
        operation = getattr(method, "operation", None)
        returning = getattr(method, "returning", None)
        declared_scopes = type(method).__dict__.get("__scopes__", _MISSING)
        safe_operation = str(operation) if operation is not None else None
        if operation is None or returning is None or declared_scopes is _MISSING:
            raise PokerlostConfigurationError(
                "Concrete Pokerlost method must declare operation, returning, and __scopes__",
                operation=safe_operation,
            )
        scopes = self._validate_scopes(declared_scopes, operation=str(operation))
        if scopes is not None and not self.has_authentication_middleware:
            raise PokerlostConfigurationError(
                "Protected operation requires PokerlostAuthenticationMiddleware",
                operation=str(operation),
            )
        call_options = options if options is not None else PokerlostRequestOptions()
        request: PokerlostRequest[object] | None = None
        with suppress(TypeError, ValueError):
            request = PokerlostRequest[object](payload=method)
        if request is None:
            raise PokerlostConfigurationError(
                "Pokerlost method payload could not be prepared",
                operation=str(operation),
            )
        call = PokerlostCall(
            method=cast("PokerlostMethod[object]", method),
            request=request,
            options=call_options,
            scopes=scopes,
        )

        async def transport(current_call: PokerlostCall) -> object:
            return await self._session.send(current_call)

        call_next: PokerlostCallNext[object] = transport
        for layer in reversed(self._middleware):
            call_next = self._wrap(layer, call_next)
        return cast(ResultT, await call_next(call))

    @staticmethod
    def _validate_scopes(value: object, *, operation: str) -> tuple[PokerlostScopes, ...] | None:
        if value is None:
            return None
        if not isinstance(value, tuple) or not value:
            raise PokerlostConfigurationError(
                "Method __scopes__ must be None or a non-empty tuple",
                operation=operation,
            )
        if any(not isinstance(scope, PokerlostScopes) for scope in value):
            raise PokerlostConfigurationError(
                "Method __scopes__ must contain only PokerlostScopes members",
                operation=operation,
            )
        scopes = cast("tuple[PokerlostScopes, ...]", value)
        if len(frozenset(scopes)) != len(scopes):
            raise PokerlostConfigurationError(
                "Method __scopes__ must not contain duplicates",
                operation=operation,
            )
        if scopes != tuple(sorted(scopes, key=lambda item: item.value)):
            raise PokerlostConfigurationError(
                "Method __scopes__ must use canonical ordering",
                operation=operation,
            )
        return scopes

    @staticmethod
    def _wrap(
        middleware: PokerlostMiddleware,
        call_next: PokerlostCallNext[object],
    ) -> PokerlostCallNext[object]:
        async def wrapped(call: PokerlostCall) -> object:
            return await middleware(call, call_next)

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
