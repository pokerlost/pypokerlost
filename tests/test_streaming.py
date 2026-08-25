from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from pypokerlost import Client, StreamMethod, UnexpectedStatusError
from tests.helpers import DummyStreamMethod, FakeTransport, make_content_stream


def test_stream_method_base_is_abstract() -> None:
    assert inspect.isabstract(StreamMethod)
    with pytest.raises(TypeError):
        StreamMethod()  # type: ignore[abstract]


def test_stream_method_is_strict_frozen_and_not_awaitable() -> None:
    method = DummyStreamMethod(file_id=42)

    assert not inspect.isawaitable(method)
    assert not hasattr(method, "__await__")

    with pytest.raises(ValidationError):
        DummyStreamMethod(file_id=42, unexpected=True)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        method.file_id = 7  # type: ignore[misc]


def test_stream_method_uses_default_rpc_request_builder() -> None:
    request = DummyStreamMethod(file_id=42).build_request()

    assert request.method == "POST"
    assert request.path == "/tests.download"
    assert request.json == {"file_id": 42}


@pytest.mark.asyncio
async def test_streaming_is_live_and_closes_after_normal_exit() -> None:
    stream, iterator, close_recorder = make_content_stream([b"first", b"second"])
    transport = FakeTransport(stream=stream)
    client = Client(base_url="https://example.test", transport=transport)

    async with client.stream_content(DummyStreamMethod(file_id=42)) as content:
        assert iterator.pulled == 0
        assert content.status_code == 200
        assert content.headers["content-type"] == "application/octet-stream"
        live_iterator = content.__aiter__()
        assert await anext(live_iterator) == b"first"
        assert iterator.pulled == 1
        assert [chunk async for chunk in live_iterator] == [b"second"]
        assert not content.is_closed

    assert content.is_closed
    assert close_recorder.calls == 1
    assert transport.open_stream_calls[0][1] == "tests.download"


@pytest.mark.asyncio
async def test_streaming_closes_after_early_iteration_break() -> None:
    stream, iterator, close_recorder = make_content_stream([b"first", b"second"])
    client = Client(
        base_url="https://example.test",
        transport=FakeTransport(stream=stream),
    )

    async with client.stream_content(DummyStreamMethod(file_id=42)) as content:
        async for chunk in content:
            assert chunk == b"first"
            break
        assert iterator.pulled == 1

    assert content.is_closed
    assert close_recorder.calls == 1


@pytest.mark.asyncio
async def test_streaming_closes_after_exception_in_caller_block() -> None:
    stream, _, close_recorder = make_content_stream([b"first"])
    client = Client(
        base_url="https://example.test",
        transport=FakeTransport(stream=stream),
    )

    with pytest.raises(RuntimeError, match="caller failure"):
        async with client.stream_content(DummyStreamMethod(file_id=42)):
            raise RuntimeError("caller failure")

    assert stream.is_closed
    assert close_recorder.calls == 1


@pytest.mark.asyncio
async def test_non_success_stream_is_closed_before_error_escapes() -> None:
    stream, iterator, close_recorder = make_content_stream(
        [b"x" * 300, b"x" * 300, b"must not be read"],
        status_code=404,
        headers={"content-type": "text/plain"},
    )
    transport = FakeTransport(stream=stream)
    client = Client(base_url="https://example.test", transport=transport)

    with pytest.raises(UnexpectedStatusError) as captured:
        async with client.stream_content(DummyStreamMethod(file_id=42)):
            pytest.fail("a non-success response must not be yielded")

    assert captured.value.status_code == 404
    assert captured.value.operation == "tests.download"
    assert len(captured.value.response_excerpt) <= 512
    assert iterator.pulled == 2
    assert stream.is_closed
    assert close_recorder.calls == 1


@pytest.mark.asyncio
async def test_content_stream_close_is_idempotent() -> None:
    stream, _, close_recorder = make_content_stream([])

    await stream.aclose()
    await stream.aclose()

    assert stream.is_closed
    assert close_recorder.calls == 1
