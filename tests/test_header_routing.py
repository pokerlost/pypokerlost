"""Verify explicit routing independently of operations, payloads and credentials."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from pypokerlost.client import PokerlostAPIServer
from pypokerlost.enums import PokerlostScopes, ServiceId
from pypokerlost.middleware._call import PokerlostCall
from pypokerlost.session import HttpxSession


@pytest.mark.parametrize("protected", [False, True])
def test_identical_operations_use_explicit_gateway_target(
    call: PokerlostCall, protected: bool
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": 7})

    if protected:
        call = replace(call, scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,)).with_access_token(
            "synthetic-routing-token"
        )

    async def exercise() -> None:
        for service in (ServiceId.AUTH, ServiceId.ACCOUNTS):
            session = HttpxSession(
                api_server=PokerlostAPIServer("https://gateway.invalid", service_id=service)
            )
            session._http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            async with session:
                assert await session.send(call) == 7

    asyncio.run(exercise())
    assert [request.headers["x-pokerlost-serviceId"] for request in requests] == [
        "authService",
        "accountsService",
    ]
    assert all(str(request.url) == "https://gateway.invalid/technicalProbe" for request in requests)
    assert all(json.loads(request.content) == {"payload": {"value": 7}} for request in requests)
    assert all(("authorization" in request.headers) == protected for request in requests)


@pytest.mark.parametrize("value", ["accountsService", "ACCOUNTSService", "", "http://127.0.0.1", 1])
def test_untyped_or_unknown_service_is_rejected(value: object) -> None:
    with pytest.raises(TypeError, match="ServiceId"):
        PokerlostAPIServer("https://gateway.invalid", service_id=value)  # type: ignore[arg-type]
