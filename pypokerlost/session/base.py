"""Asynchronous Pokerlost transport session contract."""

from __future__ import annotations

import abc
from types import TracebackType
from typing import Self

from pypokerlost.types import PokerlostAuthorizedRequest, PokerlostRequest

type PokerlostRequestEnvelope = PokerlostRequest[object] | PokerlostAuthorizedRequest[object]


class PokerlostSession(abc.ABC):
    """Send one canonical JSON envelope and return its declared typed result."""

    async def start(self) -> None:  # noqa: B027
        """Start transport resources when needed."""

    @abc.abstractmethod
    async def send[ResultT](
        self,
        request: PokerlostRequestEnvelope,
        /,
    ) -> ResultT:
        """Send one request without adding caller-controlled HTTP metadata."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Release transport resources."""

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
