from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from pypokerlost.methods import PokerlostMethod

if TYPE_CHECKING:
    from pypokerlost.client.client import Client

type MiddlewareHandler[ResultT] = Callable[
    [PokerlostMethod[ResultT]],
    Awaitable[ResultT],
]


class BaseMiddleware(abc.ABC):
    """Wrap one RPC method execution."""

    @abc.abstractmethod
    async def __call__[ResultT](
        self,
        handler: MiddlewareHandler[ResultT],
        method: PokerlostMethod[ResultT],
        client: Client,
    ) -> ResultT:
        """Wrap ``handler`` for one bound RPC method execution."""
