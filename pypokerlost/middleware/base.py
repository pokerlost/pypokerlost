"""Typed middleware contracts for one Pokerlost request envelope."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from pypokerlost.types import PokerlostAuthorizedRequest, PokerlostRequest

type PokerlostMiddlewareRequest = PokerlostRequest[object] | PokerlostAuthorizedRequest[object]
type PokerlostCallNext[ResultT] = Callable[..., Awaitable[ResultT]]


class PokerlostMiddleware(Protocol):
    """Wrap one immutable request without a registry or reflection."""

    async def __call__[ResultT](
        self,
        request: PokerlostMiddlewareRequest,
        call_next: PokerlostCallNext[ResultT],
        /,
    ) -> ResultT:
        """Continue the canonical middleware chain."""
