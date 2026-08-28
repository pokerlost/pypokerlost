"""Base contract for typed PokerLost API methods."""

from __future__ import annotations

import abc
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import ConfigDict

from pypokerlost.types import APIOperation, HTTPMethod, PokerlostType

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class PokerlostMethod[ResultT](PokerlostType, abc.ABC):
    """Typed request fields, operation metadata, and optional explicit client binding."""

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    __http_method__: ClassVar[HTTPMethod] = "POST"

    @property
    @abc.abstractmethod
    def __api_method__(self) -> APIOperation:
        """Return the complete API operation identifier."""

    @property
    @abc.abstractmethod
    def __returning__(self) -> Any:
        """Return the declared response result type."""

    async def emit(self, client: Client) -> ResultT:
        return await client(self)

    def __await__(self) -> Generator[Any, None, ResultT]:
        return self.emit(self.resolve_client()).__await__()
