from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class BaseMethod(BaseModel):
    """Immutable request data and declarative metadata for an RPC operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    __api_method__: ClassVar[str]
    __http_method__: ClassVar[str] = "POST"


class Method[ResultT](BaseMethod):
    """Typed ordinary RPC operation."""

    __returning__: ClassVar[Any]

    async def execute(self, client: Client | None = None) -> ResultT:
        """Execute through an explicit client or the task-local current client."""
        if client is None:
            from pypokerlost.client.context import get_current_client

            client = get_current_client()
        return await client.make_request(self)

    def __await__(self) -> Generator[object, None, ResultT]:
        return self.execute().__await__()


class StreamMethod(BaseMethod):
    """RPC operation whose response is consumed as a managed byte stream."""
