"""Exercise the real SDK adapter through HTTPX transport and cookie-policy boundaries."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import replace
from urllib.request import Request

import httpx
import pytest

from pypokerlost.client import PokerlostAPIServer
from pypokerlost.errors import (
    PokerlostAccessTokenExpiredError,
    PokerlostAPIError,
    PokerlostAuthenticationError,
    PokerlostAuthorizationError,
    PokerlostConfigurationError,
    PokerlostConnectionError,
    PokerlostProtocolError,
    PokerlostTimeoutError,
)
from pypokerlost.middleware._call import PokerlostCall
from pypokerlost.session import HttpxSession
from pypokerlost.session.httpx import _RejectAllCookiePolicy

type Handler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]
type Transport = Callable[[Handler], list[httpx.Request]]


@pytest.mark.parametrize(
    "url",
    [
        "https://api.invalid",
        "https://localhost/",
        "http://127.0.0.1:8123",
        "http://[::1]:8123",
        "http://localhost",
    ],
)
def test_server_accepts_origins_and_constructs_exact_operation_url(
    url: str, call: PokerlostCall
) -> None:
    server = PokerlostAPIServer(url)
    assert server.operation_url(call.method.operation) == url.rstrip("/") + "/technicalProbe"


@pytest.mark.parametrize(
    "url",
    [
        "http://api.invalid",
        "ftp://localhost",
        "https://",
        "https://user:secret@api.invalid",
        "https://user@api.invalid",
        "https://api.invalid/path",
        "https://api.invalid?q=secret",
        "https://api.invalid/#secret",
    ],
)
def test_server_rejects_insecure_or_ambient_url_state(url: str) -> None:
    with pytest.raises(ValueError):
        PokerlostAPIServer(url)


def test_server_rejects_nonstring_origin() -> None:
    with pytest.raises(TypeError):
        PokerlostAPIServer(None)


@pytest.mark.parametrize("timeout", [0, -1, True, "10", None])
def test_session_rejects_invalid_timeouts(timeout: object) -> None:
    with pytest.raises(ValueError, match="positive"):
        HttpxSession(timeout=timeout)


def test_session_lifecycle_is_idempotent_and_restartable(transport: Transport) -> None:
    requests = transport(lambda request: httpx.Response(200, json={"ok": True, "result": 7}))

    async def exercise() -> None:
        session = HttpxSession(timeout=2)
        await session.close()
        async with session as entered:
            assert entered is session
            first = session._http_client
            assert first is not None
            await session.start()
            assert session._http_client is first
        assert first.is_closed
        assert session._http_client is None
        await session.close()
        await session.start()
        second = session._http_client
        assert second is not None and second is not first
        await session.close()
        assert second.is_closed

    asyncio.run(exercise())
    assert requests == []


@pytest.mark.parametrize("protected", [False, True])
def test_wire_request_and_response_are_pure_json(
    transport: Transport, call: PokerlostCall, protected: bool
) -> None:
    requests = transport(lambda request: httpx.Response(200, json={"ok": True, "result": 7}))
    if protected:
        from pypokerlost.enums import PokerlostScopes

        call = replace(call, scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,)).with_access_token(
            "synthetic-access-secret"
        )

    async def exercise() -> None:
        async with HttpxSession(
            api_server=PokerlostAPIServer("https://api.invalid"), timeout=2
        ) as session:
            assert await session.send(call) == 7

    asyncio.run(exercise())
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.invalid/technicalProbe"
    assert json.loads(request.content) == {"payload": {"value": 7}}
    assert request.headers["content-type"] == "application/json"
    assert request.extensions["timeout"] == {"connect": 2, "read": 2, "write": 2, "pool": 2}
    if protected:
        assert request.headers["authorization"] == "Bearer synthetic-access-secret"
    else:
        assert "authorization" not in request.headers
    assert "cookie" not in request.headers


@pytest.mark.parametrize("protected", [False, True])
def test_transport_rejects_invalid_token_binding_before_io(
    transport: Transport, call: PokerlostCall, protected: bool
) -> None:
    from pypokerlost.enums import PokerlostScopes

    requests = transport(lambda request: pytest.fail("Invalid authorization must not reach I/O"))
    call = (
        replace(call, scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,))
        if protected
        else call.with_access_token("synthetic-access-secret")
    )

    async def exercise() -> None:
        async with HttpxSession() as session:
            with pytest.raises(PokerlostConfigurationError):
                await session.send(call)

    asyncio.run(exercise())
    assert requests == []


@pytest.mark.parametrize(
    ("transport_error", "sdk_error"),
    [
        (httpx.ReadTimeout, PokerlostTimeoutError),
        (httpx.ConnectError, PokerlostConnectionError),
        (httpx.ProxyError, PokerlostConnectionError),
        (httpx.RemoteProtocolError, PokerlostConnectionError),
        (httpx.LocalProtocolError, PokerlostConfigurationError),
        (TypeError, PokerlostConfigurationError),
        (ValueError, PokerlostConfigurationError),
    ],
)
def test_transport_failure_mapping_redacts_external_details(
    transport: Transport,
    call: PokerlostCall,
    transport_error: type[Exception],
    sdk_error: type[Exception],
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise transport_error("synthetic-private-transport-detail")

    requests = transport(fail)

    async def exercise() -> None:
        async with HttpxSession() as session:
            with pytest.raises(sdk_error) as error:
                await session.send(call)
            assert "synthetic-private-transport-detail" not in str(error.value)
            assert error.value.__context__ is None
            assert error.value.operation == "technicalProbe"

    asyncio.run(exercise())
    assert len(requests) == 1


def test_transport_cancellation_propagates_without_wrapping(
    transport: Transport, call: PokerlostCall
) -> None:
    def cancel(request: httpx.Request) -> httpx.Response:
        raise asyncio.CancelledError

    requests = transport(cancel)

    async def exercise() -> None:
        async with HttpxSession() as session:
            with pytest.raises(asyncio.CancelledError):
                await session.send(call)

    asyncio.run(exercise())
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("status", "code", "error_type"),
    [
        (401, "POKERLOST_ACCESS_TOKEN_EXPIRED", PokerlostAccessTokenExpiredError),
        (400, "POKERLOST_ACCESS_TOKEN_EXPIRED", PokerlostAccessTokenExpiredError),
        (401, "OTHER", PokerlostAuthenticationError),
        (400, "POKERLOST_AUTHENTICATION_REQUIRED", PokerlostAuthenticationError),
        (400, "POKERLOST_ACCESS_TOKEN_INVALID", PokerlostAuthenticationError),
        (403, "OTHER", PokerlostAuthorizationError),
        (400, "POKERLOST_INSUFFICIENT_SCOPE", PokerlostAuthorizationError),
        (429, "BUSY", PokerlostAPIError),
    ],
)
def test_api_error_classification_and_safe_metadata(
    transport: Transport,
    call: PokerlostCall,
    status: int,
    code: str,
    error_type: type[PokerlostAPIError],
) -> None:
    transport(
        lambda request: httpx.Response(
            status,
            json={"ok": False, "error": code, "error_message": "Safe message", "retry_after": 0.5},
        )
    )

    async def exercise() -> None:
        async with HttpxSession() as session:
            with pytest.raises(error_type) as error:
                await session.send(call)
            assert type(error.value) is error_type
            assert error.value.status_code == status
            assert error.value.error == code
            assert error.value.error_message == "Safe message"
            assert error.value.retry_after == 0.5
            assert error.value.operation == "technicalProbe"
            assert "Safe message" in str(error.value)
            assert not hasattr(error.value, "response")

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"synthetic-private-body"),
        httpx.Response(200, json={"private": "synthetic-private-body"}),
        httpx.Response(200, json={"ok": True, "result": "synthetic-private-body"}),
        httpx.Response(503, json={"ok": True, "result": 7}),
    ],
)
def test_protocol_failures_do_not_retain_raw_body(
    transport: Transport, call: PokerlostCall, response: httpx.Response
) -> None:
    transport(lambda request: response)

    async def exercise() -> None:
        async with HttpxSession() as session:
            with pytest.raises(PokerlostProtocolError) as error:
                await session.send(call)
            assert error.value.status_code == response.status_code
            assert "synthetic-private-body" not in str(error.value)
            assert error.value.__context__ is None
            assert not hasattr(error.value, "response")

    asyncio.run(exercise())


def test_response_cookies_cannot_become_ambient_authentication(
    transport: Transport, call: PokerlostCall
) -> None:
    requests = transport(
        lambda request: httpx.Response(
            200,
            json={"ok": True, "result": 7},
            headers={"set-cookie": "auth=synthetic-cookie-secret; Path=/; Secure"},
        )
    )

    async def exercise() -> None:
        async with HttpxSession() as session:
            assert await session.send(call) == 7
            assert await session.send(call) == 7
            assert len(session._http_client.cookies) == 0

    asyncio.run(exercise())
    assert len(requests) == 2
    assert all("cookie" not in request.headers for request in requests)


def test_cookie_policy_denies_each_standard_policy_hook() -> None:
    policy = _RejectAllCookiePolicy()
    cookie = next(iter(httpx.Cookies({"auth": "synthetic-cookie-secret"}).jar))
    request = Request("https://api.invalid/")
    assert policy.set_ok(cookie, request) is False
    assert policy.return_ok(cookie, request) is False
    assert policy.domain_return_ok("api.invalid", request) is False
    assert policy.path_return_ok("/", request) is False
