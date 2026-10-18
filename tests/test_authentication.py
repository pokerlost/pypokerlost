"""Exercise exact token state, one reactive refresh, and middleware ordering."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any

import httpx
import pytest

from pypokerlost import PokerlostClient
from pypokerlost.client import PokerlostRequestOptions
from pypokerlost.enums import PokerlostScopes
from pypokerlost.errors import (
    PokerlostAccessTokenExpiredError,
    PokerlostAuthenticationError,
    PokerlostAuthenticationStateError,
    PokerlostAuthorizationError,
    PokerlostConfigurationError,
)
from pypokerlost.methods import PokerlostMethod
from pypokerlost.middleware import (
    PokerlostAuthenticationMiddleware,
    PokerlostRetryMiddleware,
    PokerlostRetryPolicy,
)
from pypokerlost.types import PokerlostStoredToken, PokerlostToken, PokerlostTokenKey

type Transport = Callable[[Callable[[httpx.Request], httpx.Response]], list[httpx.Request]]
NOW = datetime(2030, 1, 1, tzinfo=UTC)
SCOPE = PokerlostScopes.ACCOUNTS_SELF_GET_ME


def stored(
    version: int = 1,
    *,
    audience: str = "accountsService",
    scopes: tuple[PokerlostScopes, ...] = (SCOPE,),
    expires_at: datetime = NOW + timedelta(minutes=1),
) -> PokerlostStoredToken:
    return PokerlostStoredToken(
        token=PokerlostToken(
            access_token=f"synthetic-access-{version}",
            expires_in=60,
            scopes=scopes,
            audience=audience,
        ),
        expires_at=expires_at,
        version=version,
    )


class TokenStore:
    """A service-port fake that records exact state requests and CAS expectations."""

    def __init__(self, state: PokerlostStoredToken | None) -> None:
        self.state = state
        self.loaded: list[PokerlostTokenKey] = []
        self.invalidated: list[tuple[PokerlostTokenKey, int | None]] = []

    async def load(self, key: PokerlostTokenKey, /) -> PokerlostStoredToken | None:
        self.loaded.append(key)
        return self.state

    async def save(
        self,
        key: PokerlostTokenKey,
        token: PokerlostStoredToken,
        /,
        *,
        expected_version: int | None,
    ) -> PokerlostStoredToken:
        assert self.state is not None and self.state.version == expected_version
        self.state = token
        return token

    async def invalidate(
        self, key: PokerlostTokenKey, /, *, expected_version: int | None = None
    ) -> None:
        self.invalidated.append((key, expected_version))


class Refresher:
    def __init__(self, store: TokenStore, fresh: PokerlostStoredToken) -> None:
        self.store = store
        self.fresh = fresh
        self.calls: list[tuple[PokerlostTokenKey, PokerlostStoredToken]] = []

    async def __call__(
        self, key: PokerlostTokenKey, current: PokerlostStoredToken, /
    ) -> PokerlostStoredToken:
        self.calls.append((key, current))
        return await self.store.save(key, self.fresh, expected_version=current.version)


def authentication(
    store: TokenStore,
    refresh: Refresher,
    **options: Any,
) -> PokerlostAuthenticationMiddleware:
    return PokerlostAuthenticationMiddleware(
        token_store=store,
        token_refresher=refresh,
        client_id="synthetic-client",
        audience="accountsService",
        **options,
    )


def expired() -> httpx.Response:
    return httpx.Response(401, json={"ok": False, "error": "POKERLOST_ACCESS_TOKEN_EXPIRED"})


def test_public_call_bypasses_all_token_state(
    transport: Transport, public_method: PokerlostMethod[int]
) -> None:
    requests = transport(lambda request: httpx.Response(200, json={"ok": True, "result": 7}))
    store = TokenStore(None)
    refresher = Refresher(store, stored(2))

    async def exercise() -> None:
        async with PokerlostClient(middleware=(authentication(store, refresher),)) as client:
            assert client.has_authentication_middleware
            assert await client(public_method) == 7

    asyncio.run(exercise())
    assert store.loaded == []
    assert store.invalidated == []
    assert refresher.calls == []
    assert "authorization" not in requests[0].headers


@pytest.mark.parametrize(
    "state",
    [None, stored(audience="virtualMoney"), stored(scopes=(PokerlostScopes.AUTH_CLIENT_MANAGE,))],
)
def test_missing_or_wrong_state_fails_before_io(
    transport: Transport, protected_method: PokerlostMethod[int], state: PokerlostStoredToken | None
) -> None:
    requests = transport(lambda request: pytest.fail("Unusable token state cannot reach transport"))
    store = TokenStore(state)
    refresher = Refresher(store, stored(2))

    async def exercise() -> None:
        async with PokerlostClient(middleware=(authentication(store, refresher),)) as client:
            with pytest.raises(PokerlostAuthenticationStateError) as error:
                await client(protected_method)
            assert error.value.operation == "technicalProbe"
            assert "synthetic-access" not in str(error.value)

    asyncio.run(exercise())
    assert len(store.loaded) == 1
    assert store.invalidated == []
    assert refresher.calls == []
    assert requests == []


def test_local_expiry_does_not_cause_proactive_refresh(
    transport: Transport, protected_method: PokerlostMethod[int]
) -> None:
    requests = transport(lambda request: httpx.Response(200, json={"ok": True, "result": 7}))
    store = TokenStore(stored(expires_at=datetime(2000, 1, 1, tzinfo=UTC)))
    refresher = Refresher(store, stored(2))
    auth = authentication(
        store, refresher, clock=lambda: pytest.fail("Local expiry is not a refresh trigger")
    )

    async def exercise() -> None:
        async with PokerlostClient(middleware=(auth,)) as client:
            assert await client(protected_method) == 7

    asyncio.run(exercise())
    assert requests[0].headers["authorization"] == "Bearer synthetic-access-1"
    assert refresher.calls == []
    assert store.invalidated == []


def test_expired_response_refreshes_and_replays_the_identical_wire_request_once(
    transport: Transport, protected_method: PokerlostMethod[int]
) -> None:
    requests: list[httpx.Request] = []
    requests = transport(
        lambda request: (
            expired() if len(requests) == 1 else httpx.Response(200, json={"ok": True, "result": 7})
        )
    )
    original = stored()
    store = TokenStore(original)
    refresher = Refresher(store, stored(2, expires_at=datetime.now(UTC) + timedelta(days=1)))

    async def exercise() -> None:
        async with PokerlostClient(middleware=(authentication(store, refresher),)) as client:
            assert await client(protected_method) == 7

    asyncio.run(exercise())
    assert len(requests) == 2
    assert requests[0].content == requests[1].content
    assert requests[0].url == requests[1].url
    assert [request.headers["authorization"] for request in requests] == [
        "Bearer synthetic-access-1",
        "Bearer synthetic-access-2",
    ]
    key = PokerlostTokenKey(
        client_id="synthetic-client", audience="accountsService", scopes=(SCOPE,)
    )
    assert store.loaded == [key]
    assert store.invalidated == [(key, 1)]
    assert refresher.calls == [(key, original)]


@pytest.mark.parametrize(
    ("status", "code", "kind"),
    [
        (401, "POKERLOST_ACCESS_TOKEN_INVALID", PokerlostAuthenticationError),
        (403, "POKERLOST_INSUFFICIENT_SCOPE", PokerlostAuthorizationError),
    ],
)
def test_other_auth_failures_never_refresh(
    transport: Transport,
    protected_method: PokerlostMethod[int],
    status: int,
    code: str,
    kind: type[Exception],
) -> None:
    requests = transport(lambda request: httpx.Response(status, json={"ok": False, "error": code}))
    store = TokenStore(stored())
    refresher = Refresher(store, stored(2))

    async def exercise() -> None:
        async with PokerlostClient(middleware=(authentication(store, refresher),)) as client:
            with pytest.raises(kind):
                await client(protected_method)

    asyncio.run(exercise())
    assert len(requests) == 1
    assert refresher.calls == []
    assert store.invalidated == []


@pytest.mark.parametrize(
    "fresh",
    [
        stored(1),
        stored(2, audience="virtualMoney"),
        stored(2, scopes=(PokerlostScopes.AUTH_CLIENT_MANAGE,)),
        stored(2, expires_at=NOW),
    ],
)
def test_refresher_must_return_newer_matching_unexpired_state(
    transport: Transport, protected_method: PokerlostMethod[int], fresh: PokerlostStoredToken
) -> None:
    requests = transport(lambda request: expired())
    store = TokenStore(stored())
    refresher = Refresher(store, fresh)

    async def exercise() -> None:
        async with PokerlostClient(
            middleware=(authentication(store, refresher, clock=lambda: NOW),)
        ) as client:
            with pytest.raises(PokerlostAuthenticationStateError):
                await client(protected_method)

    asyncio.run(exercise())
    assert len(requests) == 1
    assert len(refresher.calls) == 1


class UnknownOffset(tzinfo):
    def utcoffset(self, dt: datetime | None) -> None:
        return None


@pytest.mark.parametrize(
    "clock_value", [None, datetime(2030, 1, 1), datetime(2030, 1, 1, tzinfo=UnknownOffset())]
)
def test_refresh_rejects_a_nonabsolute_clock(
    transport: Transport, protected_method: PokerlostMethod[int], clock_value: object
) -> None:
    requests = transport(lambda request: expired())
    store = TokenStore(stored())
    refresher = Refresher(store, stored(2))

    async def exercise() -> None:
        auth = authentication(store, refresher, clock=lambda: clock_value)
        async with PokerlostClient(middleware=(auth,)) as client:
            with pytest.raises(PokerlostAuthenticationStateError, match="clock"):
                await client(protected_method)

    asyncio.run(exercise())
    assert len(requests) == 1


def test_refresh_allowance_is_shared_across_generic_retry_attempts(
    transport: Transport, protected_method: PokerlostMethod[int]
) -> None:
    requests: list[httpx.Request] = []
    replies = [expired(), httpx.Response(502, json={"ok": False, "error": "UPSTREAM"}), expired()]
    requests = transport(lambda request: replies[len(requests) - 1])
    store = TokenStore(stored())
    refresher = Refresher(store, stored(2))

    async def no_delay(delay: float) -> None:
        assert delay == 0.0

    async def exercise() -> None:
        auth = authentication(store, refresher, clock=lambda: NOW)
        retry = PokerlostRetryMiddleware(clock=lambda: 0.0, jitter=lambda: 0.0, sleep=no_delay)
        async with PokerlostClient(middleware=(auth, retry)) as client:
            assert client.middleware[0] is retry
            assert client.middleware[1] is auth
            with pytest.raises(PokerlostAccessTokenExpiredError):
                await client(
                    protected_method, options=PokerlostRequestOptions(PokerlostRetryPolicy())
                )

    asyncio.run(exercise())
    assert len(requests) == 3
    assert len(refresher.calls) == 1
    assert len(store.invalidated) == 1


@pytest.mark.parametrize("client_id", [None, "", True, 1])
def test_authentication_requires_an_explicit_client_identity(client_id: object) -> None:
    store = TokenStore(None)
    refresher = Refresher(store, stored(2))
    with pytest.raises(ValueError, match="client_id"):
        PokerlostAuthenticationMiddleware(
            token_store=store,
            token_refresher=refresher,
            client_id=client_id,
            audience="accountsService",
        )


@pytest.mark.parametrize("layer", ["retry", "authentication"])
def test_client_refuses_duplicate_authentication_or_retry_layers(layer: str) -> None:
    store = TokenStore(None)
    refresher = Refresher(store, stored(2))
    middleware = (
        PokerlostRetryMiddleware() if layer == "retry" else authentication(store, refresher)
    )
    with pytest.raises(PokerlostConfigurationError, match="at most one"):
        PokerlostClient(middleware=(middleware, middleware))
