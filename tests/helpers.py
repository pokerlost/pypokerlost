from __future__ import annotations

from collections.abc import AsyncIterator
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, TypeAdapter

from pypokerlost import Method, StreamMethod
from pypokerlost.transport.content_stream import ContentStream
from pypokerlost.transport.transport import Transport
from pypokerlost.transport.transport_request import TransportRequest
from pypokerlost.transport.transport_response import TransportResponse


class DummyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str


class DummyMethod(Method[DummyResult]):
    operation: ClassVar[str] = "tests.echo"

    request_value: str

    def parse_response(self, response: TransportResponse) -> DummyResult:
        return TypeAdapter(DummyResult).validate_json(response.body)


class CountingMethod(DummyMethod):
    parse_calls: ClassVar[int] = 0

    def parse_response(self, response: TransportResponse) -> DummyResult:
        type(self).parse_calls += 1
        return super().parse_response(response)


class DummyStreamMethod(StreamMethod):
    operation: ClassVar[str] = "tests.download"

    file_id: int


class RecordingByteIterator(AsyncIterator[bytes]):
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = iter(chunks)
        self.pulled = 0

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> bytes:
        try:
            chunk = next(self._chunks)
        except StopIteration as error:
            raise StopAsyncIteration from error
        self.pulled += 1
        return chunk


class CloseRecorder:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self) -> None:
        self.calls += 1


def make_content_stream(
    chunks: list[bytes],
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[ContentStream, RecordingByteIterator, CloseRecorder]:
    iterator = RecordingByteIterator(chunks)
    close_recorder = CloseRecorder()
    stream = ContentStream(
        status_code=status_code,
        headers=headers or {"content-type": "application/octet-stream"},
        byte_iterator=iterator,
        close_callback=close_recorder,
    )
    return stream, iterator, close_recorder


class FakeTransport(Transport):
    def __init__(
        self,
        *,
        response: TransportResponse | None = None,
        stream: ContentStream | None = None,
    ) -> None:
        self.response = response or success_response("ok")
        self.stream = stream
        self.execute_calls: list[tuple[TransportRequest, str | None]] = []
        self.open_stream_calls: list[tuple[TransportRequest, str | None]] = []
        self.close_calls = 0

    async def execute(
        self,
        request: TransportRequest,
        *,
        operation: str | None = None,
    ) -> TransportResponse:
        self.execute_calls.append((request, operation))
        return self.response

    async def open_stream(
        self,
        request: TransportRequest,
        *,
        operation: str | None = None,
    ) -> ContentStream:
        self.open_stream_calls.append((request, operation))
        if self.stream is None:
            raise AssertionError("A stream was not configured for this fake transport")
        return self.stream

    async def close(self) -> None:
        self.close_calls += 1


def success_response(value: str) -> TransportResponse:
    return TransportResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        body=DummyResult(value=value).model_dump_json().encode(),
    )
