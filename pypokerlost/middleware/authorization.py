"""Body-only Pokerlost access-token lifecycle middleware."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from math import isfinite
from time import monotonic
from typing import TYPE_CHECKING, Protocol, cast

from pypokerlost.errors import (
    PokerlostAuthenticationError,
    PokerlostConfigurationError,
    PokerlostProtocolError,
)
from pypokerlost.methods import GetToken, RefreshToken
from pypokerlost.types import (
    PokerlostAuthorization,
    PokerlostAuthorizedRequest,
    PokerlostClientCredentials,
    PokerlostScope,
    PokerlostToken,
    PokerlostTokenState,
    canonicalize_pokerlost_scopes,
)

from .base import PokerlostCallNext, PokerlostMiddlewareRequest

if TYPE_CHECKING:
    from pypokerlost.client import PokerlostClient


class PokerlostTokenStore(Protocol):
    """Consumer-owned token-state behavior without a persistence implementation."""

    async def load(
        self,
        *,
        audience: str,
        scopes: tuple[PokerlostScope, ...],
    ) -> PokerlostTokenState | None:
        """Load state for one audience and exact canonical scope set."""

    async def save(
        self,
        state: PokerlostTokenState,
        *,
        audience: str,
        scopes: tuple[PokerlostScope, ...],
    ) -> None:
        """Save state for one audience and exact canonical scope set."""

    async def invalidate(
        self,
        *,
        audience: str,
        scopes: tuple[PokerlostScope, ...],
    ) -> None:
        """Invalidate state for one audience and exact canonical scope set."""


class PokerlostAuthorizationMiddleware:
    """Acquire, refresh, store, and inject body-only access tokens."""

    def __init__(
        self,
        *,
        auth_client: PokerlostClient,
        token_store: PokerlostTokenStore,
        credentials: PokerlostClientCredentials,
        audience: str,
        refresh_skew: float = 30.0,
        clock: Callable[..., float] = monotonic,
    ) -> None:
        if not audience:
            raise ValueError("Pokerlost authorization audience must not be empty")
        if type(refresh_skew) is bool or not isinstance(refresh_skew, int | float):
            raise TypeError("Pokerlost refresh skew must be a number")
        if not isfinite(refresh_skew) or refresh_skew < 0.0:
            raise ValueError("Pokerlost refresh skew must be finite and non-negative")
        if auth_client.has_authorization_middleware:
            raise PokerlostConfigurationError(
                "Dedicated auth client must not use authorization middleware"
            )
        self._auth_client = auth_client
        self._token_store = token_store
        self._credentials = credentials
        self._audience = audience
        self._refresh_skew = float(refresh_skew)
        self._clock = clock
        self._locks: dict[tuple[str, tuple[PokerlostScope, ...]], asyncio.Lock] = {}

    async def __call__[ResultT](
        self,
        request: PokerlostMiddlewareRequest,
        call_next: PokerlostCallNext[ResultT],
        /,
    ) -> ResultT:
        scopes: tuple[PokerlostScope, ...] = ()
        state: PokerlostTokenState | None = None
        previous: PokerlostTokenState | None = None
        token: PokerlostToken | None = None
        authorized = cast("PokerlostAuthorizedRequest[object]", None)
        try:
            try:
                scopes = canonicalize_pokerlost_scopes(request.method.required_scopes)
            except TypeError, ValueError:
                raise PokerlostConfigurationError(
                    "Method required_scopes are invalid",
                    operation=request.method.operation,
                ) from None
            if not scopes:
                return await call_next(request)

            state = await self._usable_state(scopes)
            if state is None:
                key = (self._audience, scopes)
                lock = self._locks.setdefault(key, asyncio.Lock())
                async with lock:
                    state = await self._usable_state(scopes)
                    if state is None:
                        previous = await self._token_store.load(
                            audience=self._audience,
                            scopes=scopes,
                        )
                        acquisition_started_at = self._clock()
                        token, operation = await self._acquire_token(previous, scopes)
                        self._validate_token(token, scopes, operation=operation)
                        state = PokerlostTokenState(
                            token=token,
                            expires_at=acquisition_started_at + token.expires_in,
                        )
                        await self._token_store.save(
                            state,
                            audience=self._audience,
                            scopes=scopes,
                        )

            authorized = PokerlostAuthorizedRequest[object](
                authorization=PokerlostAuthorization(
                    access_token=state.token.access_token,
                ),
                payload=request.payload,
            ).bind_call(request.method, request.options)
            try:
                return await call_next(authorized)
            except PokerlostAuthenticationError:
                await self._token_store.invalidate(
                    audience=self._audience,
                    scopes=scopes,
                )
                raise
        finally:
            self = cast("PokerlostAuthorizationMiddleware", None)
            request = cast("PokerlostMiddlewareRequest", None)
            call_next = cast("PokerlostCallNext[ResultT]", None)
            scopes = ()
            state = None
            previous = None
            token = None
            authorized = cast("PokerlostAuthorizedRequest[object]", None)

    async def _usable_state(
        self,
        scopes: tuple[PokerlostScope, ...],
    ) -> PokerlostTokenState | None:
        state: PokerlostTokenState | None = None
        try:
            state = await self._token_store.load(
                audience=self._audience,
                scopes=scopes,
            )
            if state is None:
                return None
            if state.token.audience != self._audience or state.token.scopes != scopes:
                await self._token_store.invalidate(
                    audience=self._audience,
                    scopes=scopes,
                )
                return None
            if state.expires_at <= self._clock() + self._refresh_skew:
                return None
            return state
        finally:
            self = cast("PokerlostAuthorizationMiddleware", None)
            scopes = ()
            state = None

    async def _acquire_token(
        self,
        previous: PokerlostTokenState | None,
        scopes: tuple[PokerlostScope, ...],
    ) -> tuple[PokerlostToken, str]:
        token: PokerlostToken | None = None
        try:
            if previous is not None and previous.token.refresh_token is not None:
                try:
                    token = await self._auth_client(
                        RefreshToken(
                            refresh_token=previous.token.refresh_token,
                            scopes=scopes,
                            audience=self._audience,
                        )
                    )
                except PokerlostAuthenticationError:
                    await self._token_store.invalidate(
                        audience=self._audience,
                        scopes=scopes,
                    )
                    raise
                return token, "refreshToken"
            token = await self._auth_client(
                GetToken(
                    client_id=self._credentials.client_id,
                    client_secret=self._credentials.client_secret,
                    scopes=scopes,
                    audience=self._audience,
                )
            )
            return token, "getToken"
        finally:
            self = cast("PokerlostAuthorizationMiddleware", None)
            previous = None
            scopes = ()
            token = None

    def _validate_token(
        self,
        token: PokerlostToken,
        scopes: tuple[PokerlostScope, ...],
        *,
        operation: str,
    ) -> None:
        valid = token.audience == self._audience and token.scopes == scopes
        self = cast("PokerlostAuthorizationMiddleware", None)
        token = cast("PokerlostToken", None)
        scopes = ()
        if not valid:
            raise PokerlostProtocolError(operation=operation)
