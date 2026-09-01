"""httpx-backed asynchronous PokerLost transport session."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Never
from urllib.parse import urlencode

import httpx

from pypokerlost.client.api_server import PRODUCTION, APIServer
from pypokerlost.client.request import RequestBuilder, RequestOptions
from pypokerlost.client.response import ResponseHandler
from pypokerlost.client.retry.retry_after import parse_retry_after
from pypokerlost.exceptions import (
    ClientConnectionError,
    ClientRequestError,
    ClientTimeoutError,
    PokerlostError,
)
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import (
    APIOperation,
    HTTPMethod,
    HTTPRequestContentType,
    JSONDumps,
    JSONLoads,
    JSONValue,
)

from .base_session import DEFAULT_TIMEOUT, BaseSession


def _strict_json_dumps(value: JSONValue) -> str:
    return json.dumps(value, allow_nan=False)


def _form_urlencode(data: dict[str, JSONValue]) -> str:
    for value in data.values():
        if type(value) is str:
            continue
        if type(value) is list and all(type(item) is str for item in value):
            continue
        raise TypeError("Form request values must be strings or lists of strings")
    return urlencode(sorted(data.items()), doseq=True)


@dataclass(frozen=True, slots=True)
class _PreparedPayload:
    content: bytes = field(repr=False)
    headers: tuple[tuple[str, str], ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class _RequestSuccess[ResultT]:
    result: ResultT


@dataclass(frozen=True, slots=True)
class _RequestFailure:
    error: BaseException


type _RequestOutcome[ResultT] = _RequestSuccess[ResultT] | _RequestFailure
type _PayloadOutcome = _PreparedPayload | _RequestFailure


def _strip_exception(error: BaseException) -> BaseException:
    error = error.with_traceback(None)
    error.__cause__ = None
    error.__context__ = None
    return error


def _raise_failure(failure: _RequestFailure) -> Never:
    raise failure.error.with_traceback(None) from None


class HttpxSession(BaseSession):
    """Restartable session that lazily owns one ``httpx.AsyncClient``."""

    def __init__(
        self,
        *,
        api_server: APIServer = PRODUCTION,
        json_dumps: JSONDumps = _strict_json_dumps,
        json_loads: JSONLoads = json.loads,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        request_builder = RequestBuilder()
        response_handler = ResponseHandler(json_loads=json_loads)
        super().__init__(
            request_builder=request_builder,
            response_handler=response_handler,
            timeout=timeout,
        )
        self._api_server = api_server
        self._json_dumps = json_dumps
        self._http_client: httpx.AsyncClient | None = None
        self._lifecycle_lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._http_client is None:
                self._http_client = httpx.AsyncClient()

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        timeout: int,
        *,
        options: RequestOptions,
    ) -> ResultT:
        operation: APIOperation | None = None
        http_method: HTTPMethod | None = None
        content_type: HTTPRequestContentType | None = None
        returning: object | None = None
        setup_failure: ClientRequestError | None = None
        try:
            try:
                operation, http_method, content_type = self.request_builder.describe(method)
                returning = method.__returning__
            except Exception:
                setup_failure = ClientRequestError(
                    method=method,
                    operation=operation,
                )

            if setup_failure is None:
                if (
                    operation is None
                    or http_method is None
                    or content_type is None
                    or returning is None
                ):
                    raise AssertionError("HTTP request metadata is incomplete")
                return await self._make_request_with_metadata(
                    method,
                    operation=operation,
                    http_method=http_method,
                    content_type=content_type,
                    returning=returning,
                    timeout=timeout,
                    options=options,
                )
        finally:
            method = None  # type: ignore[assignment]
            options = RequestOptions()
            returning = None

        if setup_failure is None:
            raise AssertionError("HTTP request setup completed without a result")
        raise setup_failure from None

    async def _make_request_with_metadata[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        operation: APIOperation,
        http_method: HTTPMethod,
        content_type: HTTPRequestContentType,
        returning: object,
        timeout: int | None = None,
        options: RequestOptions | None = None,
    ) -> ResultT:
        effective_timeout = self.timeout if timeout is None else timeout
        request_options = options if options is not None else RequestOptions()
        payload: _PreparedPayload | None = None
        payload_outcome: _PayloadOutcome | None = None
        try:
            payload_outcome = self._prepare_payload(
                method=method,
                operation=operation,
                http_method=http_method,
                content_type=content_type,
                options=request_options,
            )
            if isinstance(payload_outcome, _RequestFailure):
                _raise_failure(payload_outcome)
            payload = payload_outcome
            return await self._send_request(
                method=method,
                operation=operation,
                http_method=http_method,
                returning=returning,
                content=payload.content,
                headers=payload.headers,
                timeout=effective_timeout,
            )
        finally:
            method = None  # type: ignore[assignment]
            options = None
            request_options = RequestOptions()
            payload = None
            payload_outcome = None

    def _prepare_payload[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        operation: APIOperation,
        http_method: HTTPMethod,
        content_type: HTTPRequestContentType,
        options: RequestOptions,
    ) -> _PayloadOutcome:
        try:
            request = self.request_builder.build(
                method,
                options=options,
                operation=operation,
                http_method=http_method,
                content_type=content_type,
            )
            if request.content_type == "application/json":
                serialized = self._json_dumps(request.data)
                if not isinstance(serialized, str):
                    raise TypeError("json_dumps must return str")
            else:
                serialized = _form_urlencode(request.data)
            return _PreparedPayload(
                content=serialized.encode("utf-8"),
                headers=request.headers,
            )
        except Exception:
            return _RequestFailure(
                ClientRequestError(method=method, operation=operation),
            )

    async def _send_request[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        operation: APIOperation,
        http_method: HTTPMethod,
        returning: object,
        content: bytes,
        headers: tuple[tuple[str, str], ...],
        timeout: int,
    ) -> ResultT:
        """Send one already encoded SDK-internal request through this transport."""
        url = ""
        http_client: httpx.AsyncClient | None = None
        outcome: _RequestOutcome[ResultT]
        try:
            url = self._api_server.api_url(operation)
            await self.start()
            http_client = self._http_client
            if http_client is None:
                outcome = _RequestFailure(
                    ClientRequestError(method=method, operation=operation),
                )
            else:
                outcome = await self._perform_request(
                    http_client=http_client,
                    method=method,
                    operation=operation,
                    http_method=http_method,
                    returning=returning,
                    url=url,
                    content=content,
                    headers=headers,
                    timeout=timeout,
                )
        except asyncio.CancelledError as error:
            outcome = _RequestFailure(_strip_exception(error))
        except Exception:
            outcome = _RequestFailure(
                ClientRequestError(method=method, operation=operation),
            )
        finally:
            method = None  # type: ignore[assignment]
            returning = None
            content = b""
            headers = ()
            http_client = None
            url = ""
        if isinstance(outcome, _RequestFailure):
            _raise_failure(outcome)
        return outcome.result

    async def _perform_request[ResultT](
        self,
        *,
        http_client: httpx.AsyncClient,
        method: PokerlostMethod[ResultT],
        operation: APIOperation,
        http_method: HTTPMethod,
        returning: object,
        url: str,
        content: bytes,
        headers: tuple[tuple[str, str], ...],
        timeout: int,
    ) -> _RequestOutcome[ResultT]:
        try:
            response = await http_client.request(
                method=http_method,
                url=url,
                content=content,
                headers=headers,
                timeout=timeout,
            )
        except asyncio.CancelledError as error:
            return _RequestFailure(_strip_exception(error))
        except httpx.TimeoutException:
            return _RequestFailure(
                ClientTimeoutError(method=method, operation=operation),
            )
        except httpx.NetworkError, httpx.ProxyError, httpx.RemoteProtocolError:
            return _RequestFailure(
                ClientConnectionError(method=method, operation=operation),
            )
        except (
            httpx.TransportError,
            httpx.HTTPError,
            httpx.InvalidURL,
            httpx.StreamError,
            TypeError,
            ValueError,
        ):
            return _RequestFailure(
                ClientRequestError(method=method, operation=operation),
            )
        except Exception:
            return _RequestFailure(
                ClientRequestError(method=method, operation=operation),
            )

        try:
            result = self.response_handler._handle_with_metadata(
                method=method,
                operation=operation,
                status_code=response.status_code,
                content=response.text,
                retry_after=parse_retry_after(response.headers.get("Retry-After")),
                returning=returning,
            )
        except PokerlostError as error:
            return _RequestFailure(_strip_exception(error))
        except Exception:
            return _RequestFailure(
                ClientRequestError(method=method, operation=operation),
            )
        return _RequestSuccess(result)

    async def close(self) -> None:
        async with self._lifecycle_lock:
            http_client = self._http_client
            self._http_client = None
        if http_client is not None:
            await http_client.aclose()
