"""User-defined Pokerlost application lifecycle contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pypokerlost.application import PokerlostApplication


class PokerlostApplicationLifecycle(Protocol):
    def __call__(
        self,
        application: PokerlostApplication,
        /,
    ) -> AbstractAsyncContextManager[None]: ...


@asynccontextmanager
async def default_pokerlost_application_lifecycle(
    application: PokerlostApplication,
) -> AsyncIterator[None]:
    del application
    yield
