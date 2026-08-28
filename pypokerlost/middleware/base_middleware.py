"""Typed middleware contracts for API method execution."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Protocol

from pypokerlost.client.request import RequestOptions
from pypokerlost.methods import PokerlostMethod

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class MiddlewareHandler(Protocol):
    """Execute any method through the remaining middleware chain."""

    async def __call__[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        options: RequestOptions | None = None,
    ) -> ResultT:
        """Execute ``method``, optionally replacing inherited request options."""


class BaseMiddleware(abc.ABC):
    """Wrap one API method execution."""

    @abc.abstractmethod
    async def __call__[ResultT](
        self,
        handler: MiddlewareHandler,
        method: PokerlostMethod[ResultT],
        client: Client,
        options: RequestOptions,
    ) -> ResultT:
        """Wrap ``handler`` for one bound API method execution."""
