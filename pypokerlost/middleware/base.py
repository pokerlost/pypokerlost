"""Typed middleware contracts for one Pokerlost request envelope."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from ._call import PokerlostCall

type PokerlostCallNext[ResultT] = Callable[..., Awaitable[ResultT]]


class PokerlostMiddleware(Protocol):
    """Wrap one immutable request without a registry or reflection."""

    async def __call__[ResultT](
        self,
        call: PokerlostCall,
        call_next: PokerlostCallNext[ResultT],
        /,
    ) -> ResultT:
        """Continue the canonical middleware chain."""
