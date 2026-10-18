"""Client configuration, plugin ordering and task-local method execution."""

from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
from collections.abc import Awaitable, Callable

import httpx
import pytest

import pypokerlost
from pypokerlost import PokerlostClient
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.client.current_client import get_current_client
from pypokerlost.enums import PokerlostScopes
from pypokerlost.errors import PokerlostConfigurationError
from pypokerlost.methods import (
    PokerlostMethod,
    ProvisionHuman,
    RefreshToken,
    ReplacePrincipalScopes,
)
from pypokerlost.middleware._call import PokerlostCall
from pypokerlost.session import HttpxSession, PokerlostSession

type Transport = Callable[[Callable[[httpx.Request], httpx.Response]], list[httpx.Request]]


def test_distribution_version_fallback_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    installed_version = pypokerlost.__version__

    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    with monkeypatch.context() as metadata:
        metadata.setattr(importlib.metadata, "version", missing)
        importlib.reload(pypokerlost)
        assert pypokerlost.__version__ == "0+unknown"
    importlib.reload(pypokerlost)
    assert pypokerlost.__version__ == installed_version


def test_client_owns_explicit_session_or_server_but_not_both() -> None:
    session = HttpxSession()
    client = PokerlostClient(session=session)
    assert client.session is session
    assert client.has_authentication_middleware is False
    with pytest.raises(PokerlostConfigurationError, match="either session or server"):
        PokerlostClient(session=session, server=PokerlostAPIServer("https://api.invalid"))
    assert isinstance(
        PokerlostClient(server=PokerlostAPIServer("https://api.invalid")).session, HttpxSession
    )


@pytest.mark.parametrize(
    "scopes",
    [
        [],
        (),
        ("accounts.self.getMe",),
        (PokerlostScopes.ACCOUNTS_SELF_GET_ME,) * 2,
        (PokerlostScopes.AUTH_CLIENT_MANAGE, PokerlostScopes.ACCOUNTS_SELF_GET_ME),
    ],
)
def test_noncanonical_method_scopes_fail_before_io(
    transport: Transport, public_method: PokerlostMethod[int], scopes: object
) -> None:
    requests = transport(lambda request: pytest.fail("Invalid scope metadata cannot reach I/O"))
    invalid = type("InvalidMethod", (type(public_method),), {"__scopes__": scopes})()

    async def exercise() -> None:
        async with PokerlostClient() as client:
            with pytest.raises(PokerlostConfigurationError) as error:
                await client(invalid)
            assert error.value.operation == "technicalProbe"

    asyncio.run(exercise())
    assert requests == []


def test_concrete_methods_must_declare_metadata_directly(
    transport: Transport, public_method: PokerlostMethod[int]
) -> None:
    inherited = type("InheritedMethod", (type(public_method),), {})()
    requests = transport(lambda request: pytest.fail("Missing metadata cannot reach I/O"))

    async def exercise() -> None:
        async with PokerlostClient() as client:
            for invalid in (object(), inherited, PokerlostMethod[int]()):
                with pytest.raises(PokerlostConfigurationError):
                    await client(invalid)

    asyncio.run(exercise())
    assert requests == []


def test_public_methods_require_an_active_current_client(
    public_method: PokerlostMethod[int],
) -> None:
    with pytest.raises(PokerlostConfigurationError, match="No PokerlostClient"):
        get_current_client()

    async def exercise() -> None:
        with pytest.raises(PokerlostConfigurationError, match="No PokerlostClient"):
            await public_method

    asyncio.run(exercise())


def test_nested_clients_restore_task_local_execution_target(
    transport: Transport, public_method: PokerlostMethod[int]
) -> None:
    requests = transport(lambda request: httpx.Response(200, json={"ok": True, "result": 7}))

    async def exercise() -> None:
        one = PokerlostClient(server=PokerlostAPIServer("https://one.invalid"))
        two = PokerlostClient(server=PokerlostAPIServer("https://two.invalid"))
        assert await one.start() is one
        await one.stop()
        async with one:
            assert get_current_client() is one
            assert await public_method == 7
            with pytest.raises(PokerlostConfigurationError, match="already active"):
                await one.__aenter__()
            async with two:
                assert get_current_client() is two
                assert await public_method == 7
            assert get_current_client() is one
            assert await public_method == 7
        await one.__aexit__(None, None, None)
        with pytest.raises(PokerlostConfigurationError):
            get_current_client()

    asyncio.run(exercise())
    assert [request.url.host for request in requests] == [
        "one.invalid",
        "two.invalid",
        "one.invalid",
    ]


def test_custom_middleware_preserves_declared_order(
    transport: Transport, public_method: PokerlostMethod[int]
) -> None:
    events: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        events.append("transport")
        return httpx.Response(200, json={"ok": True, "result": 7})

    transport(respond)

    class Trace:
        def __init__(self, name: str) -> None:
            self.name = name

        async def __call__(
            self, call: PokerlostCall, call_next: Callable[..., Awaitable[object]]
        ) -> object:
            events.append(self.name + " enter")
            result = await call_next(call)
            events.append(self.name + " exit")
            return result

    async def exercise() -> None:
        async with PokerlostClient(middleware=(Trace("one"), Trace("two"))) as client:
            assert await client(public_method) == 7

    asyncio.run(exercise())
    assert events == ["one enter", "two enter", "transport", "two exit", "one exit"]


def test_failed_transport_start_resets_client_context_for_a_later_attempt() -> None:
    class Transport(PokerlostSession):
        def __init__(self) -> None:
            self.starts = 0
            self.closes = 0

        async def start(self) -> None:
            self.starts += 1
            if self.starts == 1:
                raise OSError("synthetic unavailable transport")

        async def send[ResultT](self, call: PokerlostCall, /) -> ResultT:
            raise AssertionError("This lifecycle test does not send requests")

        async def close(self) -> None:
            self.closes += 1

    async def exercise() -> None:
        session = Transport()
        client = PokerlostClient(session=session)
        with pytest.raises(OSError, match="unavailable transport"):
            async with client:
                pytest.fail("Startup failed")
        with pytest.raises(PokerlostConfigurationError):
            get_current_client()
        async with client:
            assert get_current_client() is client
        assert session.starts == 2
        assert session.closes == 1

    asyncio.run(exercise())


def test_method_contracts_validate_existing_scope_fields() -> None:
    from uuid import UUID

    identity = UUID(int=1)
    assert (
        ProvisionHuman(
            business_operation_id=identity, account_id=identity, initial_scopes=[]
        ).initial_scopes
        == ()
    )
    assert (
        ReplacePrincipalScopes(
            business_operation_id=identity, principal_id=identity, scopes=[]
        ).scopes
        == ()
    )
    assert (
        RefreshToken(refresh_token="synthetic-refresh-secret", audience="accountsService").scopes
        is None
    )
    refresh = RefreshToken(
        refresh_token="synthetic-refresh-secret",
        audience="accountsService",
        scopes=[PokerlostScopes.ACCOUNTS_SELF_GET_ME],
    )
    assert refresh.scopes == (PokerlostScopes.ACCOUNTS_SELF_GET_ME,)
    assert "synthetic-refresh-secret" not in repr(refresh)
