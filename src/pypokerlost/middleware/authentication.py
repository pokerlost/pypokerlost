"""Header authentication with one narrow reactive refresh boundary."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pypokerlost.errors import (
    PokerlostAccessTokenExpiredError,
    PokerlostAuthenticationStateError,
)
from pypokerlost.types import PokerlostAudience, PokerlostStoredToken, PokerlostTokenKey

from ._call import PokerlostCall, claim_reactive_refresh
from .base import PokerlostCallNext


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PokerlostTokenStore(Protocol):
    """Consumer-owned persistent, shared, compare-and-swap token state."""

    async def load(self, key: PokerlostTokenKey, /) -> PokerlostStoredToken | None:
        """Load one exact client/audience/scope token state."""

    async def save(
        self,
        key: PokerlostTokenKey,
        token: PokerlostStoredToken,
        /,
        *,
        expected_version: int | None,
    ) -> PokerlostStoredToken:
        """Persist encrypted state only if the expected version still matches."""

    async def invalidate(
        self,
        key: PokerlostTokenKey,
        /,
        *,
        expected_version: int | None = None,
    ) -> None:
        """Invalidate one exact version when it is still current."""


class PokerlostTokenRefresher(Protocol):
    """Service-owned cross-process refresh coordination port."""

    async def __call__(
        self,
        key: PokerlostTokenKey,
        current: PokerlostStoredToken,
        /,
    ) -> PokerlostStoredToken:
        """Coordinate refresh and return the persisted current version."""


class PokerlostAuthenticationMiddleware:
    """Load shared state, inject a bearer token, and recover expiration once."""

    def __init__(
        self,
        *,
        token_store: PokerlostTokenStore,
        token_refresher: PokerlostTokenRefresher,
        client_id: str,
        audience: PokerlostAudience | str,
        clock: Callable[..., datetime] = _utc_now,
    ) -> None:
        if type(client_id) is not str or not client_id:
            raise ValueError("Pokerlost authentication client_id must be a non-empty str")
        self._token_store = token_store
        self._token_refresher = token_refresher
        self._client_id = client_id
        self._audience = PokerlostAudience(audience)
        self._clock = clock

    async def __call__[ResultT](
        self,
        call: PokerlostCall,
        call_next: PokerlostCallNext[ResultT],
        /,
    ) -> ResultT:
        if call.scopes is None:
            return await call_next(call)

        key = PokerlostTokenKey(
            client_id=self._client_id,
            audience=self._audience,
            scopes=call.scopes,
        )
        current = await self._token_store.load(key)
        if current is None:
            raise PokerlostAuthenticationStateError(
                "No stored access token is available",
                operation=str(call.method.operation),
            )
        self._validate_state_key(
            key,
            current,
            operation=str(call.method.operation),
            source="Token store",
        )

        authorized = call.with_access_token(current.token.access_token)
        try:
            return await call_next(authorized)
        except PokerlostAccessTokenExpiredError:
            if not claim_reactive_refresh():
                raise
            await self._token_store.invalidate(key, expected_version=current.version)
            fresh = await self._refresh(key, current, operation=str(call.method.operation))
            return await call_next(call.with_access_token(fresh.token.access_token))

    async def _refresh(
        self,
        key: PokerlostTokenKey,
        current: PokerlostStoredToken,
        *,
        operation: str,
    ) -> PokerlostStoredToken:
        fresh = await self._token_refresher(key, current)
        if fresh.version <= current.version:
            raise PokerlostAuthenticationStateError(
                "Token refresher did not return a newer stored version",
                operation=operation,
            )
        self._validate_state_key(key, fresh, operation=operation, source="Token refresher")
        if fresh.expires_at <= self._now(operation=operation):
            raise PokerlostAuthenticationStateError(
                "Token refresher returned expired state",
                operation=operation,
            )
        return fresh

    @staticmethod
    def _validate_state_key(
        key: PokerlostTokenKey,
        state: PokerlostStoredToken,
        *,
        operation: str,
        source: str,
    ) -> None:
        if state.token.audience != key.audience or state.token.scopes != key.scopes:
            raise PokerlostAuthenticationStateError(
                f"{source} returned state for a different token key",
                operation=operation,
            )

    def _now(self, *, operation: str) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise PokerlostAuthenticationStateError(
                "Authentication clock must return a timezone-aware datetime",
                operation=operation,
            )
        return value.astimezone(UTC)
