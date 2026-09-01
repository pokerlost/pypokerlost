"""Typed middleware contracts for one immutable API call context."""

from __future__ import annotations

import abc
from types import TracebackType
from typing import Protocol, Self

from pypokerlost.client.request import RequestOptions
from pypokerlost.middleware.context import APIMiddlewareContext


class APIMiddlewareCallNext[ResultT](Protocol):
    """Execute the captured method through the remaining middleware chain."""

    async def __call__(
        self,
        *,
        options: RequestOptions | None = None,
    ) -> ResultT:
        """Continue, optionally replacing immutable transport options."""


class APIMiddleware(abc.ABC):
    """Wrap one API call without access to its body or declared result type."""

    @abc.abstractmethod
    async def __call__[ResultT](
        self,
        call_next: APIMiddlewareCallNext[ResultT],
        context: APIMiddlewareContext,
    ) -> ResultT:
        """Wrap ``call_next`` for one immutable call context."""

    async def start(self) -> None:  # noqa: B027
        """Start owned resources; the default implementation is a no-op."""

    async def close(self) -> None:  # noqa: B027
        """Release owned resources; the default implementation is a no-op."""

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
