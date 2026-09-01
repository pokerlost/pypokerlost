"""httpx-backed body-only Pokerlost JSON transport."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from http.cookiejar import Cookie, CookieJar, DefaultCookiePolicy
from typing import Never, cast

import httpx
from pydantic import TypeAdapter, ValidationError

from pypokerlost.client.pokerlost_api_server import (
    DEFAULT_POKERLOST_API_SERVER,
    PokerlostAPIServer,
)
from pypokerlost.errors import (
    PokerlostAPIError,
    PokerlostAuthenticationError,
    PokerlostAuthorizationError,
    PokerlostConfigurationError,
    PokerlostConnectionError,
    PokerlostError,
    PokerlostProtocolError,
    PokerlostTimeoutError,
)
from pypokerlost.types import (
    PokerlostAuthorizedRequest,
    PokerlostResponse,
)

from .base import PokerlostRequestEnvelope, PokerlostSession

DEFAULT_TIMEOUT_SECONDS = 10.0
_AUTHENTICATION_ERRORS = frozenset(
    {
        "AUTHENTICATION_REQUIRED",
        "INVALID_ACCESS_TOKEN",
        "INVALID_CLIENT_CREDENTIALS",
        "INVALID_REFRESH_TOKEN",
    }
)
_AUTHORIZATION_ERRORS = frozenset({"INSUFFICIENT_SCOPE"})


@dataclass(frozen=True, slots=True)
class _Success[ResultT]:
    result: ResultT


@dataclass(frozen=True, slots=True)
class _Failure:
    error: PokerlostError


type _Outcome[ResultT] = _Success[ResultT] | _Failure


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


def _raise_failure(failure: _Failure) -> Never:
    raise failure.error.with_traceback(None) from None


class HttpxSession(PokerlostSession):
    """Own one restartable HTTPX client and use only its normal JSON API."""

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

    async def send[ResultT](
        self,
        request: PokerlostRequestEnvelope,
        /,
    ) -> ResultT:
        outcome = cast("_Outcome[ResultT]", None)
        try:
            outcome = await self._send_outcome(request)
            if isinstance(outcome, _Failure):
                _raise_failure(outcome)
            return outcome.result
        finally:
            request = cast("PokerlostRequestEnvelope", None)
            outcome = cast("_Outcome[ResultT]", None)

    async def _send_outcome[ResultT](
        self,
        request: PokerlostRequestEnvelope,
    ) -> _Outcome[ResultT]:
        response: httpx.Response | None = None
        try:
            operation = request.method.operation
            if request.method.required_scopes and not isinstance(
                request,
                PokerlostAuthorizedRequest,
            ):
                return _Failure(
                    PokerlostConfigurationError(
                        "Protected operation requires PokerlostAuthorizationMiddleware",
                        operation=operation,
                    )
                )
            if not request.method.required_scopes and isinstance(
                request,
                PokerlostAuthorizedRequest,
            ):
                return _Failure(
                    PokerlostConfigurationError(
                        "Public operation cannot carry authorization",
                        operation=operation,
                    )
                )

            await self.start()
            http_client = self._http_client
            if http_client is None:
                return _Failure(
                    PokerlostConfigurationError(
                        "Pokerlost HTTP session failed to start",
                        operation=operation,
                    )
                )
            try:
                response = await http_client.post(
                    self._api_server.operation_url(operation),
                    json=request.model_dump(mode="json", by_alias=False),
                    timeout=self._timeout,
                )
            except asyncio.CancelledError:
                raise
            except httpx.TimeoutException:
                return _Failure(PokerlostTimeoutError(operation=operation))
            except httpx.NetworkError, httpx.ProxyError, httpx.RemoteProtocolError:
                return _Failure(PokerlostConnectionError(operation=operation))
            except httpx.HTTPError, TypeError, ValueError:
                return _Failure(
                    PokerlostConfigurationError(
                        "Pokerlost HTTP request could not be prepared",
                        operation=operation,
                    )
                )

            return self._decode_response(
                operation=operation,
                status_code=response.status_code,
                decoded=self._decode_json(response, operation=operation),
                returning=request.method.returning,
                client=request.method.client,
            )
        except asyncio.CancelledError:
            raise
        except PokerlostError as error:
            return _Failure(error.with_traceback(None))
        finally:
            request = cast("PokerlostRequestEnvelope", None)
            response = None

    def _decode_json(
        self,
        response: httpx.Response,
        *,
        operation: str,
    ) -> object | PokerlostProtocolError:
        try:
            decoded: object = response.json()
            return decoded
        except ValueError:
            return PokerlostProtocolError(
                operation=operation,
                status_code=response.status_code,
            )

    def _decode_response[ResultT](
        self,
        *,
        operation: str,
        status_code: int,
        decoded: object | PokerlostProtocolError,
        returning: object,
        client: object,
    ) -> _Outcome[ResultT]:
        if isinstance(decoded, PokerlostProtocolError):
            return _Failure(decoded)
        try:
            envelope = TypeAdapter(PokerlostResponse[object]).validate_python(
                decoded,
                strict=True,
            )
        except ValidationError:
            return _Failure(PokerlostProtocolError(operation=operation, status_code=status_code))

        if not envelope.ok:
            error_code = cast(str, envelope.error)
            error_type: type[PokerlostAPIError]
            if status_code == 401 or error_code in _AUTHENTICATION_ERRORS:
                error_type = PokerlostAuthenticationError
            elif status_code == 403 or error_code in _AUTHORIZATION_ERRORS:
                error_type = PokerlostAuthorizationError
            else:
                error_type = PokerlostAPIError
            return _Failure(
                error_type(
                    operation=operation,
                    status_code=status_code,
                    error=error_code,
                    error_message=envelope.error_message,
                    retry_after=envelope.retry_after,
                )
            )

        if not 200 <= status_code < 300:
            return _Failure(PokerlostProtocolError(operation=operation, status_code=status_code))
        try:
            encoded_result = json.dumps(
                envelope.result,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            result: object = TypeAdapter(returning).validate_json(
                encoded_result,
                strict=True,
                context={"client": client},
            )
        except TypeError, ValueError, UnicodeError, ValidationError:
            return _Failure(PokerlostProtocolError(operation=operation, status_code=status_code))
        return _Success(cast(ResultT, result))

    async def close(self) -> None:
        async with self._lifecycle_lock:
            http_client = self._http_client
            self._http_client = None
        if http_client is not None:
            await http_client.aclose()
