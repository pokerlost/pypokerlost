"""Asynchronous access-token provider contract."""

from __future__ import annotations

import abc
from types import TracebackType
from typing import Self

from .access_token import AccessToken


class AccessTokenProvider(abc.ABC):
    """Resolve secret-safe access tokens for bearer middleware."""

    @abc.abstractmethod
    async def get_access_token(self) -> AccessToken:
        """Return a cached or newly acquired access token."""

    async def start(self) -> None:  # noqa: B027
        """Start owned resources; the default implementation is a no-op."""

    async def close(self) -> None:  # noqa: B027
        """Release resources and token references; the default is a no-op."""

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
