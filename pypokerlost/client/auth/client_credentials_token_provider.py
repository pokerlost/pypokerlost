"""OAuth2 client-credentials provider using the canonical PokerLost transport."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from math import isfinite
from time import monotonic
from typing import Annotated, Final, Literal
from urllib.parse import urlencode

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from pypokerlost.client.api_server import APIServer
from pypokerlost.client.session import DEFAULT_TIMEOUT
from pypokerlost.client.session.httpx_session import HttpxSession
from pypokerlost.exceptions import (
    ClientDecodeError,
    ClientStateError,
    MiddlewareConfigurationError,
)
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import APIOperation

from .access_token import AccessToken
from .access_token_provider import AccessTokenProvider
from .client_credentials import ClientCredentials

_TOKEN_OPERATION: Final[APIOperation] = "oauth.token"
_TOKEN_HEADERS = (
    ("Content-Type", "application/x-www-form-urlencoded"),
    ("Accept", "application/json"),
)

type _OAuthScope = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+$",
    ),
]
type _ResourceIndicator = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^urn:pokerlost:service:[a-z][A-Za-z0-9]*$",
    ),
]
type _RefreshSkew = Annotated[
    float,
    Field(strict=True, ge=0.0, le=3600.0, allow_inf_nan=False),
]
type _RequestTimeout = Annotated[int, Field(strict=True, gt=0, le=300)]
type _ExpiresIn = Annotated[int, Field(strict=True, gt=0)]

_SCOPES_ADAPTER: TypeAdapter[tuple[_OAuthScope, ...]] = TypeAdapter(
    tuple[_OAuthScope, ...],
    config=ConfigDict(strict=True),
)
_RESOURCE_ADAPTER: TypeAdapter[_ResourceIndicator] = TypeAdapter(_ResourceIndicator)
_REFRESH_SKEW_ADAPTER: TypeAdapter[_RefreshSkew] = TypeAdapter(_RefreshSkew)
_REQUEST_TIMEOUT_ADAPTER: TypeAdapter[_RequestTimeout] = TypeAdapter(_RequestTimeout)


class _OAuthTokenResponse(BaseModel):
    """Typed result carried by the standard PokerLost response envelope."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    access_token: SecretStr = Field(repr=False, exclude=True, min_length=1)
    token_type: Literal["bearer"]
    expires_in: _ExpiresIn
    scope: str

    @field_validator("scope")
    @classmethod
    def validate_canonical_scope(cls, value: str) -> str:
        """Require a sorted, unique, space-delimited OAuth2 scope string."""
        values = tuple(value.split(" "))
        try:
            parsed = _SCOPES_ADAPTER.validate_python(values)
        except ValidationError as error:
            raise ValueError("Token scope is invalid") from error
        if not parsed or parsed != tuple(sorted(set(parsed))):
            raise ValueError("Token scope must be non-empty, unique, and sorted")
        return value


class _OAuthTokenMethod(PokerlostMethod[_OAuthTokenResponse]):
    """SDK-internal method metadata for the focused form/Basic token request."""

    __api_method__ = _TOKEN_OPERATION
    __http_method__ = "POST"
    __returning__ = _OAuthTokenResponse


class _ClientCredentialsTokenSession(HttpxSession):
    """Encode the one non-JSON request while reusing canonical transport/decoding."""

    async def request_token(
        self,
        *,
        credentials: ClientCredentials,
        scopes: tuple[_OAuthScope, ...],
        resource: _ResourceIndicator,
        timeout: int,
    ) -> _OAuthTokenResponse:
        form = urlencode(
            (
                ("grant_type", "client_credentials"),
                ("scope", " ".join(scopes)),
                ("resource", resource),
            ),
        ).encode("ascii")
        basic_input = b""
        basic_value = ""
        method: _OAuthTokenMethod | None = None
        try:
            try:
                basic_input = (
                    f"{credentials.client_id}:{credentials.client_secret.get_secret_value()}"
                ).encode()
            except UnicodeEncodeError:
                raise MiddlewareConfigurationError(
                    "Client credentials cannot be encoded for HTTP Basic authentication",
                ) from None
            basic_value = base64.b64encode(basic_input).decode("ascii")
            method = _OAuthTokenMethod()
            return await self._send_request(
                method=method,
                operation=_TOKEN_OPERATION,
                http_method="POST",
                returning=_OAuthTokenResponse,
                content=form,
                headers=(*_TOKEN_HEADERS, ("Authorization", f"Basic {basic_value}")),
                timeout=timeout,
            )
        finally:
            form = b""
            basic_input = b""
            basic_value = ""
            method = None


@dataclass(frozen=True, slots=True)
class _CachedAccessToken:
    token: AccessToken
    expires_at: float


class ClientCredentialsTokenProvider(AccessTokenProvider):
    """Acquire and single-flight cache OAuth2 client-credentials tokens."""

    def __init__(
        self,
        *,
        api_server: APIServer,
        credentials: ClientCredentials,
        scopes: frozenset[str],
        resource: str,
        refresh_skew: float = 30.0,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        try:
            parsed_scopes = _SCOPES_ADAPTER.validate_python(tuple(scopes))
            parsed_resource = _RESOURCE_ADAPTER.validate_python(resource)
            parsed_refresh_skew = _REFRESH_SKEW_ADAPTER.validate_python(refresh_skew)
            parsed_timeout = _REQUEST_TIMEOUT_ADAPTER.validate_python(timeout)
        except ValidationError as error:
            raise ValueError(
                "Client credentials token provider configuration is invalid"
            ) from error
        if not parsed_scopes:
            raise ValueError("Client credentials token provider requires at least one scope")

        self._credentials = credentials
        self._scopes = tuple(sorted(parsed_scopes))
        self._resource = parsed_resource
        self._refresh_skew = parsed_refresh_skew
        self._timeout = parsed_timeout
        self._session = _ClientCredentialsTokenSession(
            api_server=api_server,
            timeout=parsed_timeout,
        )
        self._cache: _CachedAccessToken | None = None
        self._refresh_task: asyncio.Task[AccessToken] | None = None
        self._refresh_lock = asyncio.Lock()
        self._closed = False

    async def start(self) -> None:
        async with self._refresh_lock:
            await self._session.start()
            self._closed = False

    async def get_access_token(self) -> AccessToken:
        cached: AccessToken | None = None
        refresh_task: asyncio.Task[AccessToken] | None = None
        async with self._refresh_lock:
            if self._closed:
                raise ClientStateError(
                    "Access token provider is closed; call start() before reuse",
                )
            cached = self._usable_cached_token()
            if cached is not None:
                return cached
            refresh_task = self._refresh_task
            if refresh_task is not None and refresh_task.done():
                if not refresh_task.cancelled():
                    refresh_task.exception()
                self._refresh_task = None
                refresh_task = None
            if refresh_task is None:
                refresh_task = asyncio.create_task(self._acquire_and_cache())
                self._refresh_task = refresh_task
                refresh_task.add_done_callback(self._forget_refresh_task)

        try:
            return await asyncio.shield(refresh_task)
        finally:
            cached = None
            refresh_task = None

    async def close(self) -> None:
        async with self._refresh_lock:
            self._closed = True
            refresh_task = self._refresh_task
            self._refresh_task = None
            self._cache = None
            if refresh_task is not None and not refresh_task.done():
                refresh_task.cancel()
            if refresh_task is not None:
                await asyncio.gather(refresh_task, return_exceptions=True)
            self._cache = None
            await self._session.close()

    def _usable_cached_token(self) -> AccessToken | None:
        cached = self._cache
        if cached is None:
            return None
        if monotonic() + self._refresh_skew >= cached.expires_at:
            return None
        return cached.token

    async def _acquire_and_cache(self) -> AccessToken:
        response: _OAuthTokenResponse | None = None
        token: AccessToken | None = None
        acquisition_started_at = monotonic()
        try:
            response = await self._session.request_token(
                credentials=self._credentials,
                scopes=self._scopes,
                resource=self._resource,
                timeout=self._timeout,
            )
            response_scopes = tuple(response.scope.split(" "))
            if response_scopes != self._scopes:
                raise ClientDecodeError(
                    method=_OAuthTokenMethod(),
                    operation=_TOKEN_OPERATION,
                    status_code=200,
                ) from ValueError("Token scope does not match the request")

            token_failure: bool
            try:
                token = AccessToken(
                    value=response.access_token,
                    token_type=response.token_type,
                    expires_in=response.expires_in,
                    scopes=response_scopes,
                )
            except TypeError, ValueError, ValidationError:
                token = None
                token_failure = True
            else:
                token_failure = False
            if token_failure or token is None:
                raise ClientDecodeError(
                    method=_OAuthTokenMethod(),
                    operation=_TOKEN_OPERATION,
                    status_code=200,
                ) from ValueError("Access token validation failed")
            try:
                expires_at = acquisition_started_at + float(response.expires_in)
            except OverflowError:
                expires_at = float("inf")
            if not isfinite(expires_at):
                raise ClientDecodeError(
                    method=_OAuthTokenMethod(),
                    operation=_TOKEN_OPERATION,
                    status_code=200,
                ) from ValueError("Access token expiration is not representable")
            if monotonic() >= expires_at:
                raise ClientDecodeError(
                    method=_OAuthTokenMethod(),
                    operation=_TOKEN_OPERATION,
                    status_code=200,
                ) from ValueError("Access token expired during acquisition")
            self._cache = _CachedAccessToken(
                token=token,
                expires_at=expires_at,
            )
            return token
        finally:
            response = None
            token = None

    def _forget_refresh_task(self, completed: asyncio.Task[AccessToken]) -> None:
        if self._refresh_task is completed:
            self._refresh_task = None
        if not completed.cancelled():
            completed.exception()
