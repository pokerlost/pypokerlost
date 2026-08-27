from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Protocol

from pypokerlost.methods import PokerlostMethod
from pypokerlost.request import RPCRequestOptions

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class MiddlewareHandler(Protocol):
    """Execute any method through the remaining middleware chain."""

    async def __call__[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        options: RPCRequestOptions | None = None,
    ) -> ResultT:
        """Execute ``method``, optionally replacing inherited request options."""


class BaseMiddleware(abc.ABC):
    """Wrap one RPC method execution."""

    @abc.abstractmethod
    async def __call__[ResultT](
        self,
        handler: MiddlewareHandler,
        method: PokerlostMethod[ResultT],
        client: Client,
        options: RPCRequestOptions,
    ) -> ResultT:
        """Wrap ``handler`` for one bound RPC method execution."""
