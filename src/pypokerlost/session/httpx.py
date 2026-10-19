"""HTTPX-backed Pokerlost JSON transport."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from http.cookiejar import Cookie, CookieJar, DefaultCookiePolicy
from typing import cast

import httpx
from pydantic import TypeAdapter, ValidationError

from pypokerlost.client.pokerlost_api_server import (
    DEFAULT_POKERLOST_API_SERVER,
    SERVICE_ID_HEADER,
    PokerlostAPIServer,
)
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
from pypokerlost.types import PokerlostResponse

from .base import PokerlostSession

DEFAULT_TIMEOUT_SECONDS = 10.0
_EXPIRED_ERROR = "POKERLOST_ACCESS_TOKEN_EXPIRED"
_AUTHENTICATION_ERRORS = frozenset(
    {
        "POKERLOST_AUTHENTICATION_REQUIRED",
        "POKERLOST_ACCESS_TOKEN_INVALID",
    }
)
_AUTHORIZATION_ERRORS = frozenset({"POKERLOST_INSUFFICIENT_SCOPE"})


class _RejectAllCookiePolicy(DefaultCookiePolicy):
    """Prevent ambient response state from becoming request authentication."""

    def set_ok(self, cookie: Cookie, request: object) -> bool:
        del cookie, request
        return False

    def return_ok(self, cookie: Cookie, request: object) -> bool:
        del cookie, request
        return False

    def domain_return_ok(self, domain: str, request: object) -> bool:
        del domain, request
        return False

    def path_return_ok(self, path: str, request: object) -> bool:
        del path, request
        return False


class HttpxSession(PokerlostSession):
    """Own one restartable HTTPX client and the sole bearer-header adapter."""

    def __init__(
        self,
        *,
        api_server: PokerlostAPIServer = DEFAULT_POKERLOST_API_SERVER,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if type(timeout) is bool or not isinstance(timeout, int | float) or timeout <= 0:
            raise ValueError("Pokerlost session timeout must be positive")
        self._api_server = api_server
        self._timeout = float(timeout)
        self._http_client: httpx.AsyncClient | None = None
        self._lifecycle_lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(
                    cookies=CookieJar(policy=_RejectAllCookiePolicy()),
                    trust_env=False,
                )

    async def send[ResultT](self, call: PokerlostCall, /) -> ResultT:
        operation = str(call.method.operation)
        if call.scopes is None and call.access_token is not None:
            raise PokerlostConfigurationError(
                "Public operation cannot carry an access token",
                operation=operation,
            )
        if call.scopes is not None and call.access_token is None:
            raise PokerlostConfigurationError(
                "Protected operation requires an access token",
                operation=operation,
            )

        await self.start()
        http_client = self._http_client
        if http_client is None:
            raise PokerlostConfigurationError(
                "Pokerlost HTTP session failed to start",
                operation=operation,
            )
        response: httpx.Response | None = None
        transport_error: (
            PokerlostTimeoutError | PokerlostConnectionError | PokerlostConfigurationError | None
        ) = None
        headers: dict[str, str] = {}
        if self._api_server.service_id is not None:
            headers[SERVICE_ID_HEADER] = self._api_server.service_id.value
        if call.access_token is not None:
            headers["Authorization"] = f"Bearer {call.access_token.get_secret_value()}"
        try:
            response = await http_client.post(
                self._api_server.operation_url(call.method.operation),
                json=call.request.model_dump(mode="json", by_alias=False),
                headers=headers,
                timeout=self._timeout,
            )
        except asyncio.CancelledError:
            raise
        except httpx.TimeoutException:
            transport_error = PokerlostTimeoutError(operation=operation)
        except httpx.NetworkError, httpx.ProxyError, httpx.RemoteProtocolError:
            transport_error = PokerlostConnectionError(operation=operation)
        except httpx.HTTPError, TypeError, ValueError:
            transport_error = PokerlostConfigurationError(
                "Pokerlost HTTP request could not be prepared",
                operation=operation,
            )

        if transport_error is not None:
            raise transport_error
        if response is None:
            raise PokerlostConfigurationError(
                "Pokerlost HTTP request produced no response",
                operation=operation,
            )

        json_failed = False
        try:
            decoded: object = response.json()
        except ValueError:
            json_failed = True
            decoded = None
        if json_failed:
            raise PokerlostProtocolError(
                operation=operation,
                status_code=response.status_code,
            )
        return cast(
            ResultT,
            self._decode_response(
                operation=operation,
                status_code=response.status_code,
                decoded=decoded,
                returning=call.method.returning,
            ),
        )

    @staticmethod
    def _decode_response(
        *,
        operation: str,
        status_code: int,
        decoded: object,
        returning: object,
    ) -> object:
        envelope: PokerlostResponse[object] | None = None
        with suppress(ValidationError):
            envelope = TypeAdapter(PokerlostResponse[object]).validate_python(decoded, strict=True)
        if envelope is None:
            raise PokerlostProtocolError(
                operation=operation,
                status_code=status_code,
            )

        if not envelope.ok:
            error_code = cast(str, envelope.error)
            error_type: type[PokerlostAPIError]
            if error_code == _EXPIRED_ERROR:
                error_type = PokerlostAccessTokenExpiredError
            elif status_code == 401 or error_code in _AUTHENTICATION_ERRORS:
                error_type = PokerlostAuthenticationError
            elif status_code == 403 or error_code in _AUTHORIZATION_ERRORS:
                error_type = PokerlostAuthorizationError
            else:
                error_type = PokerlostAPIError
            raise error_type(
                operation=operation,
                status_code=status_code,
                error=error_code,
                error_message=envelope.error_message,
                retry_after=envelope.retry_after,
            ) from None

        if not 200 <= status_code < 300:
            raise PokerlostProtocolError(operation=operation, status_code=status_code)
        result_failed = False
        try:
            result: object = TypeAdapter(returning).validate_python(envelope.result)
        except TypeError, ValueError, ValidationError:
            result_failed = True
            result = None
        if result_failed:
            raise PokerlostProtocolError(
                operation=operation,
                status_code=status_code,
            )
        return result

    async def close(self) -> None:
        async with self._lifecycle_lock:
            http_client = self._http_client
            self._http_client = None
        if http_client is not None:
            await http_client.aclose()
