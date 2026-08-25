from __future__ import annotations

from abc import ABC, abstractmethod

from pypokerlost.transport.content_stream import ContentStream
from pypokerlost.transport.transport_request import TransportRequest
from pypokerlost.transport.transport_response import TransportResponse


class Transport(ABC):
    """HTTP-independent asynchronous transport contract."""

    @abstractmethod
    async def execute(
        self,
        request: TransportRequest,
        *,
        operation: str | None = None,
    ) -> TransportResponse:
        """Execute and fully read an ordinary request."""

    @abstractmethod
    async def open_stream(
        self,
        request: TransportRequest,
        *,
        operation: str | None = None,
    ) -> ContentStream:
        """Open a live response stream without pre-buffering its body."""

    @abstractmethod
    async def close(self) -> None:
        """Release transport resources. Repeated calls must be safe."""
