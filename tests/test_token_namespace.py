"""Preserve legacy persistence while opting into environment-bound token keys."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from pypokerlost import Environment, PokerlostClient, PokerlostEnvironmentConfig
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.enums import PokerlostScopes, ServiceId
from pypokerlost.errors import PokerlostAuthenticationStateError, PokerlostConfigurationError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.middleware import PokerlostAuthenticationMiddleware
from pypokerlost.session import HttpxSession, PokerlostSession
from pypokerlost.types import PokerlostStoredToken, PokerlostToken, PokerlostTokenKey


def legacy_key() -> PokerlostTokenKey:
    return PokerlostTokenKey(
        client_id="synthetic-client",
        audience="accountsService",
        scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,),
    )


def test_legacy_key_keeps_exact_three_field_model_dump() -> None:
    assert legacy_key().model_dump(mode="json") == {
        "client_id": "synthetic-client",
        "audience": "accountsService",
        "scopes": ["accounts.self.getMe"],
    }


def test_legacy_key_keeps_exact_model_dump_json_and_roundtrip() -> None:
    persisted = (
        '{"client_id":"synthetic-client","audience":"accountsService",'
        '"scopes":["accounts.self.getMe"]}'
    )
    assert legacy_key().model_dump_json() == persisted
    assert PokerlostTokenKey.model_validate_json(persisted) == legacy_key()


def bound_key(
    environment: Environment = Environment.TEST, origin: str = "https://test.invalid"
) -> PokerlostTokenKey:
    return PokerlostTokenKey(**legacy_key().model_dump(), environment=environment, origin=origin)


def state(version: int = 1, *, key: PokerlostTokenKey | None = None) -> PokerlostStoredToken:
    return PokerlostStoredToken(
        token=PokerlostToken(
            access_token=f"synthetic-namespace-{version}",
            expires_in=60,
            audience="accountsService",
            scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,),
        ),
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
        version=version,
        key=key,
    )


class NamespaceStore:
    """Test port keyed by the complete serialized identity, with per-key CAS."""

    def __init__(self, states: dict[str, PokerlostStoredToken]) -> None:
        self.states = states
        self.loaded: list[PokerlostTokenKey] = []
        self.invalidated: list[tuple[PokerlostTokenKey, int | None]] = []
        self.saved: list[tuple[PokerlostTokenKey, int | None]] = []

    async def load(self, key: PokerlostTokenKey, /) -> PokerlostStoredToken | None:
        self.loaded.append(key)
        return self.states.get(key.model_dump_json())

    async def save(
        self,
        key: PokerlostTokenKey,
        token: PokerlostStoredToken,
        /,
        *,
        expected_version: int | None,
    ) -> PokerlostStoredToken:
        current = self.states.get(key.model_dump_json())
        assert (current.version if current else None) == expected_version
        self.saved.append((key, expected_version))
        self.states[key.model_dump_json()] = token
        return token

    async def invalidate(
        self, key: PokerlostTokenKey, /, *, expected_version: int | None = None
    ) -> None:
        self.invalidated.append((key, expected_version))


def config(
    environment: Environment = Environment.TEST, origin: str = "https://test.invalid"
) -> PokerlostEnvironmentConfig:
    return PokerlostEnvironmentConfig(environment, {environment: origin})


def authentication(
    store: NamespaceStore, target: PokerlostAPIServer | None
) -> PokerlostAuthenticationMiddleware:
    async def refresh(
        key: PokerlostTokenKey, current: PokerlostStoredToken, /
    ) -> PokerlostStoredToken:
        return await store.save(
            key, state(current.version + 1, key=key), expected_version=current.version
        )

    return PokerlostAuthenticationMiddleware(
        token_store=store,
        token_refresher=refresh,
        client_id="synthetic-client",
        audience="accountsService",
        server=target,
    )


def test_bound_keys_include_namespace_and_roundtrip_without_changing_legacy_records() -> None:
    expected = {
        "environment": "test",
        "origin": "https://test.invalid",
        **legacy_key().model_dump(mode="json"),
    }
    key = bound_key()
    assert key.model_dump(mode="json") == expected
    assert json.loads(key.model_dump_json()) == expected
    assert PokerlostTokenKey.model_validate_json(key.model_dump_json()) == key
    assert (
        len(
            {
                legacy_key(),
                key,
                bound_key(Environment.DEV),
                bound_key(origin="https://other.invalid"),
            }
        )
        == 4
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"environment": Environment.TEST},
        {"origin": "https://test.invalid"},
        {"environment": Environment.TEST, "origin": ""},
        {"environment": "test", "origin": "https://test.invalid"},
    ],
)
def test_namespace_fields_are_paired_and_strict(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PokerlostTokenKey(**legacy_key().model_dump(), **fields)


@pytest.mark.parametrize(
    "target",
    [
        None,
        PokerlostAPIServer("https://other.invalid", environment=Environment.TEST),
        PokerlostAPIServer("https://test.invalid", environment=Environment.DEV),
    ],
)
def test_factory_rejects_unbound_or_mismatched_auth_before_any_io(
    target: PokerlostAPIServer | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = NamespaceStore({})

    async def forbidden_start(self: HttpxSession) -> None:
        pytest.fail("Rejected authentication must not start transport")

    monkeypatch.setattr(HttpxSession, "start", forbidden_start)
    with pytest.raises(PokerlostConfigurationError, match="does not match"):
        PokerlostClient.for_environment(config(), middleware=(authentication(store, target),))
    assert not store.loaded and not store.saved and not store.invalidated


def test_bound_auth_cannot_be_reused_on_another_environment_origin_or_legacy_client() -> None:
    store = NamespaceStore({})
    auth = authentication(store, config().server())
    first = PokerlostClient.for_environment(config(), middleware=(auth,))
    second = PokerlostClient.for_environment(
        config(origin="https://TEST.invalid:443/"), middleware=(auth,)
    )
    assert first.session is not second.session
    for destination in (config(Environment.DEV), config(origin="https://other.invalid")):
        with pytest.raises(PokerlostConfigurationError, match="does not match"):
            PokerlostClient.for_environment(destination, middleware=(auth,))
    with pytest.raises(PokerlostConfigurationError, match="does not match"):
        PokerlostClient(server=PokerlostAPIServer("https://test.invalid"), middleware=(auth,))
    assert store.loaded == []


def test_namespaced_store_does_not_fall_back_to_legacy_credentials(
    transport, protected_method: PokerlostMethod[int]
) -> None:
    requests = transport(lambda request: httpx.Response(200, json={"ok": True, "result": 7}))
    legacy = state()
    store = NamespaceStore({legacy_key().model_dump_json(): legacy})

    async def exercise() -> None:
        async with PokerlostClient.for_environment(
            config(),
            service_id=ServiceId.ACCOUNTS,
            middleware=(authentication(store, config().server()),),
        ) as client:
            with pytest.raises(PokerlostAuthenticationStateError, match="No stored"):
                await client(protected_method)
            assert requests == []
            # Owner-controlled acquisition/persistence is explicit; SDK did not copy legacy data.
            store.states[bound_key().model_dump_json()] = state(2, key=bound_key())
            assert await client(protected_method) == 7

    asyncio.run(exercise())
    assert store.loaded == [bound_key(), bound_key()]
    assert store.states[legacy_key().model_dump_json()] is legacy
    assert requests[0].headers["Authorization"] == "Bearer synthetic-namespace-2"
    assert requests[0].headers["x-pokerlost-serviceId"] == "accountsService"
    assert str(requests[0].url) == "https://test.invalid/technicalProbe"
    assert json.loads(requests[0].content) == {"payload": {"value": 7}}


def test_expired_refresh_cas_updates_only_the_selected_namespace(
    transport, protected_method: PokerlostMethod[int]
) -> None:
    requests = []
    requests = transport(
        lambda request: (
            httpx.Response(401, json={"ok": False, "error": "POKERLOST_ACCESS_TOKEN_EXPIRED"})
            if len(requests) == 1
            else httpx.Response(200, json={"ok": True, "result": 7})
        )
    )
    original = state(key=bound_key())
    untouched = state(9)
    other = bound_key(Environment.DEV)
    store = NamespaceStore(
        {
            bound_key().model_dump_json(): original,
            other.model_dump_json(): untouched,
            legacy_key().model_dump_json(): untouched,
        }
    )

    async def exercise() -> None:
        async with PokerlostClient.for_environment(
            config(), middleware=(authentication(store, config().server()),)
        ) as client:
            assert await client(protected_method) == 7

    asyncio.run(exercise())
    assert store.invalidated == [(bound_key(), 1)]
    assert store.saved == [(bound_key(), 1)]
    assert store.states[bound_key().model_dump_json()].version == 2
    assert store.states[other.model_dump_json()] is untouched
    assert store.states[legacy_key().model_dump_json()] is untouched
    assert requests[0].content == requests[1].content
    assert requests[0].url == requests[1].url


@pytest.mark.parametrize("phase", ["load", "refresh"])
def test_cancellation_propagates_without_writing_another_namespace(
    phase: str, transport, protected_method: PokerlostMethod[int]
) -> None:
    requests = transport(
        lambda request: httpx.Response(
            401, json={"ok": False, "error": "POKERLOST_ACCESS_TOKEN_EXPIRED"}
        )
    )
    original = state(key=bound_key())
    other = bound_key(Environment.DEV)

    async def exercise() -> None:
        entered = asyncio.Event()
        never = asyncio.Event()

        class BlockingStore(NamespaceStore):
            async def load(self, key: PokerlostTokenKey, /) -> PokerlostStoredToken | None:
                if phase == "load":
                    entered.set()
                    await never.wait()
                return await super().load(key)

        store = BlockingStore(
            {
                bound_key().model_dump_json(): original,
                other.model_dump_json(): original,
            }
        )

        async def refresh(key: PokerlostTokenKey, current: PokerlostStoredToken, /):
            assert key == bound_key() and current is original
            entered.set()
            await never.wait()
            pytest.fail("Cancelled refresh must not finish")

        auth = PokerlostAuthenticationMiddleware(
            token_store=store,
            token_refresher=refresh,
            client_id="synthetic-client",
            audience="accountsService",
            server=config().server(),
        )
        async with PokerlostClient.for_environment(config(), middleware=(auth,)) as client:
            task = asyncio.create_task(client(protected_method))
            async with asyncio.timeout(1):
                await entered.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
        assert not store.saved
        assert store.states[other.model_dump_json()] is original
        assert store.states[bound_key().model_dump_json()] is original
        assert store.invalidated == ([(bound_key(), 1)] if phase == "refresh" else [])

    asyncio.run(exercise())
    assert len(requests) == (1 if phase == "refresh" else 0)


def test_environment_public_call_bypasses_token_ports(
    transport, public_method: PokerlostMethod[int]
) -> None:
    requests = transport(lambda request: httpx.Response(200, json={"ok": True, "result": 7}))
    store = NamespaceStore({})

    async def exercise() -> None:
        async with PokerlostClient.for_environment(
            config(), middleware=(authentication(store, config().server()),)
        ) as client:
            assert await client(public_method) == 7

    asyncio.run(exercise())
    assert not store.loaded and not store.saved and not store.invalidated
    assert "authorization" not in requests[0].headers


def test_legacy_direct_clients_keep_their_existing_origin_independent_store_key(
    transport, protected_method: PokerlostMethod[int]
) -> None:
    requests = transport(lambda request: httpx.Response(200, json={"ok": True, "result": 7}))
    store = NamespaceStore({legacy_key().model_dump_json(): state()})
    auth = authentication(store, None)

    async def exercise() -> None:
        for origin in ("https://one.invalid", "https://two.invalid"):
            async with PokerlostClient(
                server=PokerlostAPIServer(origin), middleware=(auth,)
            ) as client:
                assert await client(protected_method) == 7

    asyncio.run(exercise())
    assert store.loaded == [legacy_key(), legacy_key()]
    assert [request.url.host for request in requests] == ["one.invalid", "two.invalid"]


@pytest.mark.parametrize(
    "returned_key",
    [
        None,
        bound_key(Environment.DEV),
        bound_key(origin="https://other.invalid"),
    ],
)
def test_namespace_rejects_legacy_store_that_ignores_new_identity_fields(
    returned_key: PokerlostTokenKey | None, transport, protected_method: PokerlostMethod[int]
) -> None:
    requests = transport(lambda request: pytest.fail("Unbound legacy state reached HTTP"))
    legacy = state(key=returned_key)

    class LegacyFallbackStore(NamespaceStore):
        async def load(self, key: PokerlostTokenKey, /) -> PokerlostStoredToken | None:
            self.loaded.append(key)
            return legacy

    store = LegacyFallbackStore({})

    async def exercise() -> None:
        async with PokerlostClient.for_environment(
            config(), middleware=(authentication(store, config().server()),)
        ) as client:
            with pytest.raises(PokerlostAuthenticationStateError, match="namespace"):
                await client(protected_method)

    asyncio.run(exercise())
    assert requests == []
    assert store.loaded == [bound_key()]
    assert not store.saved and not store.invalidated


def test_legacy_stored_state_keeps_its_three_field_serialization() -> None:
    original = state()
    assert set(original.model_dump()) == {"token", "expires_at", "version"}
    assert "key" not in json.loads(original.model_dump_json())
    # Persistence owns secret serialization; this assertion covers the local state metadata only.
    bound = state(key=bound_key())
    assert bound.model_dump(mode="json")["key"] == bound_key().model_dump(mode="json")


@pytest.mark.parametrize("returned_key", [None, bound_key(Environment.DEV)])
def test_namespaced_refresh_rejects_missing_or_wrong_state_provenance(
    returned_key: PokerlostTokenKey | None, transport, protected_method: PokerlostMethod[int]
) -> None:
    requests = transport(
        lambda request: httpx.Response(
            401, json={"ok": False, "error": "POKERLOST_ACCESS_TOKEN_EXPIRED"}
        )
    )
    store = NamespaceStore({bound_key().model_dump_json(): state(key=bound_key())})

    async def refresh(key: PokerlostTokenKey, current: PokerlostStoredToken, /):
        assert key == bound_key() and current.version == 1
        return state(2, key=returned_key)

    auth = PokerlostAuthenticationMiddleware(
        token_store=store,
        token_refresher=refresh,
        client_id="synthetic-client",
        audience="accountsService",
        server=config().server(),
    )

    async def exercise() -> None:
        async with PokerlostClient.for_environment(config(), middleware=(auth,)) as client:
            with pytest.raises(PokerlostAuthenticationStateError, match="namespace"):
                await client(protected_method)

    asyncio.run(exercise())
    assert len(requests) == 1
    assert store.invalidated == [(bound_key(), 1)]
    assert not store.saved


def test_bound_authentication_rejects_a_custom_session_without_a_verified_target() -> None:
    class CustomSession(PokerlostSession):
        async def send(self, call, /):
            pytest.fail("Rejected custom session must not send")

        async def close(self):
            pytest.fail("Rejected custom session must not start")

    store = NamespaceStore({})
    with pytest.raises(PokerlostConfigurationError, match="does not match"):
        PokerlostClient(
            session=CustomSession(), middleware=(authentication(store, config().server()),)
        )
    assert store.loaded == []
