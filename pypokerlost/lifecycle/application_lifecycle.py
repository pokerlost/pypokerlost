from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pypokerlost.application import Application


class ApplicationLifecycle(Protocol):
    """Create one user-defined context around application execution."""

    def __call__(
        self,
        application: Application,
        /,
    ) -> AbstractAsyncContextManager[None]: ...


@asynccontextmanager
async def default_application_lifecycle(
    application: Application,
) -> AsyncIterator[None]:
    """Provide the default no-op application lifecycle."""
    yield
