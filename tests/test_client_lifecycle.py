from __future__ import annotations

import pytest

from pypokerlost import (
    Client,
    ClientClosedError,
    ClientContextError,
    UnexpectedStatusError,
)
from pypokerlost.transport.transport_response import TransportResponse
from tests.helpers import (
    DummyMethod,
    DummyStreamMethod,
    FakeTransport,
    make_content_stream,
    success_response,
)


@pytest.mark.asyncio
async def test_closed_client_rejects_ordinary_and_streaming_use() -> None:
    stream, _, _ = make_content_stream([b"unused"])
    transport = FakeTransport(response=success_response("unused"), stream=stream)
    client = Client(base_url="https://example.test", transport=transport)
    await client.close()

    with pytest.raises(ClientClosedError):
        await client.make_request(DummyMethod(request_value="request"))
    with pytest.raises(ClientContextError):
        await DummyMethod(request_value="request")

    with pytest.raises(ClientClosedError):
        async with client.stream_content(DummyStreamMethod(file_id=1)):
            pytest.fail("a closed client must not yield content")

    assert transport.execute_calls == []
    assert transport.open_stream_calls == []


@pytest.mark.asyncio
async def test_injected_transport_is_not_owned_by_default_and_close_is_idempotent() -> None:
    transport = FakeTransport()
    client = Client(base_url="https://example.test", transport=transport)

    await client.close()
    await client.close()

    assert transport.close_calls == 0


@pytest.mark.asyncio
async def test_explicitly_owned_injected_transport_is_closed_once() -> None:
    transport = FakeTransport()
    client = Client(
        base_url="https://example.test",
        transport=transport,
        owns_transport=True,
    )

    await client.close()
    await client.close()

    assert transport.close_calls == 1


@pytest.mark.asyncio
async def test_non_success_response_is_rejected_before_parsing() -> None:
    response = TransportResponse(
        status_code=503,
        headers={"content-type": "text/plain"},
        body=b"temporarily unavailable",
    )
    transport = FakeTransport(response=response)
    client = Client(base_url="https://example.test", transport=transport)

    with pytest.raises(UnexpectedStatusError) as captured:
        await client.make_request(DummyMethod(request_value="request"))

    assert captured.value.status_code == 503
    assert captured.value.operation == "tests.echo"


@pytest.mark.asyncio
async def test_async_client_scope_restores_context_even_when_body_raises() -> None:
    transport = FakeTransport(response=success_response("unused"))
    client = Client(base_url="https://example.test", transport=transport)

    with pytest.raises(RuntimeError, match="caller failure"):
        async with client:
            raise RuntimeError("caller failure")

    with pytest.raises(ClientClosedError):
        await client.make_request(DummyMethod(request_value="request"))
    with pytest.raises(ClientContextError):
        await DummyMethod(request_value="request")
