from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest

from pypokerlost import TransportError
from pypokerlost.transport.httpx_transport import HttpxTransport
from pypokerlost.transport.transport_request import TransportRequest


@pytest.mark.asyncio
async def test_httpx_transport_joins_paths_merges_headers_and_copies_response() -> None:
    received_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        return httpx.Response(
            status_code=201,
            headers={"x-response": "copied"},
            content=b'{"value":"created"}',
        )

    default_headers = {"x-default": "default", "x-overridden": "old"}
    request_headers = {"x-request": "request", "x-overridden": "new"}
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = HttpxTransport(
        "https://example.test/rpc/",
        default_headers=default_headers,
        client=async_client,
    )
    request = TransportRequest(
        method="POST",
        path="/tests.echo",
        query={"page": 2},
        json={"request_value": "payload"},
        headers=request_headers,
    )

    response = await transport.execute(request, operation="tests.echo")

    assert response.status_code == 201
    assert response.headers["x-response"] == "copied"
    assert response.body == b'{"value":"created"}'
    assert len(received_requests) == 1
    sent = received_requests[0]
    assert str(sent.url) == "https://example.test/rpc/tests.echo?page=2"
    assert sent.headers["x-default"] == "default"
    assert sent.headers["x-request"] == "request"
    assert sent.headers["x-overridden"] == "new"
    assert default_headers == {"x-default": "default", "x-overridden": "old"}
    assert request_headers == {"x-request": "request", "x-overridden": "new"}

    await transport.close()


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
@pytest.mark.asyncio
async def test_known_httpx_failures_map_to_transport_error_with_cause(
    error_type: type[httpx.TransportError],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error_type("simulated transport failure", request=request)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = HttpxTransport("https://example.test", client=async_client)
    request = TransportRequest(method="GET", path="/tests.echo")

    with pytest.raises(TransportError) as captured:
        await transport.execute(request, operation="tests.echo")

    assert captured.value.operation == "tests.echo"
    assert isinstance(captured.value.__cause__, error_type)

    await transport.close()


@pytest.mark.asyncio
async def test_cancellation_is_not_mapped_to_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise asyncio.CancelledError

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = HttpxTransport("https://example.test", client=async_client)

    with pytest.raises(asyncio.CancelledError):
        await transport.execute(TransportRequest(method="GET", path="/tests.echo"))

    await transport.close()


@pytest.mark.asyncio
async def test_open_stream_failure_maps_to_transport_error_with_cause() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated stream open failure", request=request)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = HttpxTransport("https://example.test", client=async_client)

    with pytest.raises(TransportError) as captured:
        await transport.open_stream(
            TransportRequest(method="GET", path="/tests.download"),
            operation="tests.download",
        )

    assert captured.value.operation == "tests.download"
    assert isinstance(captured.value.__cause__, httpx.ConnectError)

    await transport.close()


class TrackingHttpxStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.pulled = 0
        self.close_calls = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            self.pulled += 1
            yield chunk

    async def aclose(self) -> None:
        self.close_calls += 1


class FailingHttpxStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.close_calls = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"first"
        request = httpx.Request("GET", "https://example.test/tests.download")
        raise httpx.ReadError("simulated stream read failure", request=request)

    async def aclose(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_httpx_stream_remains_live_and_closes_underlying_response() -> None:
    source = TrackingHttpxStream([b"first", b"second"])

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/octet-stream"},
            stream=source,
        )

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = HttpxTransport("https://example.test", client=async_client)

    content = await transport.open_stream(
        TransportRequest(method="GET", path="/tests.download"),
        operation="tests.download",
    )

    assert source.pulled == 0
    assert [chunk async for chunk in content] == [b"first", b"second"]
    assert source.pulled == 2
    await content.aclose()
    assert source.close_calls == 1

    await transport.close()


@pytest.mark.asyncio
async def test_stream_iteration_failure_maps_to_transport_error_with_cause() -> None:
    source = FailingHttpxStream()

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(status_code=200, stream=source)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = HttpxTransport("https://example.test", client=async_client)
    content = await transport.open_stream(
        TransportRequest(method="GET", path="/tests.download"),
        operation="tests.download",
    )

    assert await anext(content) == b"first"
    with pytest.raises(TransportError) as captured:
        await anext(content)

    assert captured.value.operation == "tests.download"
    assert isinstance(captured.value.__cause__, httpx.ReadError)

    await content.aclose()
    assert source.close_calls == 1
    await transport.close()
