"""Synthetic protocol fixtures; no service, credentials or network is required."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from http.cookiejar import CookieJar
from typing import ClassVar

import httpx
import pytest

from pypokerlost.client import PokerlostRequestOptions
from pypokerlost.enums import PokerlostScopes
from pypokerlost.methods import PokerlostMethod
from pypokerlost.middleware._call import PokerlostCall
from pypokerlost.types import PokerlostOperation, PokerlostRequest


class PublicProbe(PokerlostMethod[int]):
    operation: ClassVar[PokerlostOperation] = PokerlostOperation("technicalProbe")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = None
    returning: ClassVar[object] = int
    value: int = 7


class ProtectedProbe(PublicProbe):
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = (
        PokerlostScopes.ACCOUNTS_SELF_GET_ME,
    )


@pytest.fixture
def public_method() -> PokerlostMethod[int]:
    return PublicProbe()


@pytest.fixture
def protected_method() -> PokerlostMethod[int]:
    return ProtectedProbe()


@pytest.fixture
def call(public_method: PokerlostMethod[int]) -> PokerlostCall:
    return PokerlostCall(
        method=public_method,
        request=PokerlostRequest[object](payload=public_method),
        options=PokerlostRequestOptions(),
        scopes=None,
    )


type ResponseHandler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Callable[[ResponseHandler], list[httpx.Request]]:
    """Replace only the external HTTPX I/O boundary, preserving SDK client configuration."""
    original = httpx.AsyncClient

    def install(handler: ResponseHandler) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response | Awaitable[httpx.Response]:
            requests.append(request)
            return handler(request)

        def create_client(*, cookies: CookieJar, trust_env: bool) -> httpx.AsyncClient:
            assert trust_env is False
            return original(
                cookies=cookies, trust_env=trust_env, transport=httpx.MockTransport(respond)
            )

        monkeypatch.setattr(httpx, "AsyncClient", create_client)
        return requests

    return install
