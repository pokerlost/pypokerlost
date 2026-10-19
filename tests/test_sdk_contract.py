"""Exercise the actual HTTP adapter and authorization boundary without a network."""

from __future__ import annotations

import asyncio
import json
from typing import ClassVar
from uuid import UUID

import httpx
import pytest

from pypokerlost import PokerlostClient
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.enums import PokerlostScopes
from pypokerlost.errors import PokerlostConfigurationError, PokerlostProtocolError
from pypokerlost.methods import GetToken, PokerlostMethod
from pypokerlost.session import HttpxSession
from pypokerlost.types import PokerlostOperation


def _get_token() -> GetToken:
    return GetToken(
        client_id=UUID("2f64e790-0cf0-4de2-8fb2-5d8cf169ee42"),
        client_secret="test-only-secret",
        scopes=(PokerlostScopes.ACCOUNTS_SELF_GET_ME,),
        audience="accountsService",
    )


def test_public_token_call_uses_pure_json_and_closes_transport() -> None:
    """The public method sends no bearer header and decodes the canonical body."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "access_token": "test-only-token",
                    "refresh_token": None,
                    "expires_in": 60,
                    "scopes": [PokerlostScopes.ACCOUNTS_SELF_GET_ME.value],
                    "audience": "accountsService",
                },
                "error": None,
                "error_message": None,
                "retry_after": None,
            },
        )

    session = HttpxSession(api_server=PokerlostAPIServer("http://127.0.0.1:8123"))
    session._http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))

    async def exercise() -> None:
        async with PokerlostClient(session=session) as client:
            token = await client(_get_token())
            assert token.access_token == "test-only-token"
            assert token.expires_in == 60
        assert session._http_client is None

    asyncio.run(exercise())
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "http://127.0.0.1:8123/getToken"
    assert "Authorization" not in request.headers
    assert set(json.loads(request.content)) == {"payload"}
    assert json.loads(request.content)["payload"]["client_secret"] == "test-only-secret"


def test_malformed_success_never_exposes_response_body() -> None:
    """Malformed success data raises a safe protocol error."""
    session = HttpxSession(api_server=PokerlostAPIServer("http://127.0.0.1:8123"))
    session._http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"private": "test-only-secret"})
        )
    )

    async def exercise() -> None:
        async with PokerlostClient(session=session) as client:
            with pytest.raises(PokerlostProtocolError) as error:
                await client(_get_token())
            assert "test-only-secret" not in str(error.value)

    asyncio.run(exercise())


class ProtectedMethod(PokerlostMethod[None]):
    """A test operation with an exact protected scope."""

    operation: ClassVar[PokerlostOperation] = PokerlostOperation("probe")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = (
        PokerlostScopes.ACCOUNTS_SELF_GET_ME,
    )
    returning: ClassVar[object] = type(None)


def test_protected_operation_requires_real_authentication_layer() -> None:
    """A protected call fails before transport without a verifier boundary."""

    async def exercise() -> None:
        async with PokerlostClient() as client:
            with pytest.raises(PokerlostConfigurationError, match="requires"):
                await client(ProtectedMethod())

    asyncio.run(exercise())
