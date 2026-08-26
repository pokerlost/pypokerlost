from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from types import MappingProxyType
from typing import Protocol, Self, runtime_checkable


@runtime_checkable
class _ClosableAsyncIterator(Protocol):
    async def aclose(self) -> None: ...


class ContentStream:
    """Live response bytes with one underlying-response close callback."""

    __slots__ = (
        "_byte_iterator",
        "_close_callback",
        "_closed",
        "_headers",
        "_status_code",
    )

    def __init__(
        self,
        *,
        status_code: int,
        headers: Mapping[str, str],
        byte_iterator: AsyncIterator[bytes],
        close_callback: Callable[[], Awaitable[None]],
    ) -> None:
        self._status_code = status_code
        self._headers: Mapping[str, str] = MappingProxyType(dict(headers))
        self._byte_iterator = byte_iterator
        self._close_callback = close_callback
        self._closed = False

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def headers(self) -> Mapping[str, str]:
        return self._headers

    @property
    def is_closed(self) -> bool:
        return self._closed

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> bytes:
        if self._closed:
            raise RuntimeError("Content stream is closed")
        return bytes(await anext(self._byte_iterator))

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if isinstance(self._byte_iterator, _ClosableAsyncIterator):
                await self._byte_iterator.aclose()
        finally:
            await self._close_callback()
