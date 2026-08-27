from __future__ import annotations

from abc import ABC
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import ConfigDict

from pypokerlost.client.context_controller import ClientContextController
from pypokerlost.enums import ServiceName

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class PokerlostMethod[ResultT](ClientContextController, ABC):
    """Typed request fields, RPC metadata, and optional explicit client binding."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_default=True,
        arbitrary_types_allowed=True,
    )

    __service__: ClassVar[ServiceName]
    __api_method__: ClassVar[str]
    __http_method__: ClassVar[str] = "POST"
    __returning__: ClassVar[Any]

    async def emit(self, client: Client) -> ResultT:
        return await client(self)

    def __await__(self) -> Generator[Any, None, ResultT]:
        return self.emit(self.resolve_client()).__await__()
