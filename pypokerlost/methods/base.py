"""Base contract for typed Pokerlost API methods."""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, ClassVar, cast

from pydantic import ConfigDict

from pypokerlost.types.base import PokerlostType
from pypokerlost.types.pokerlost_operation import PokerlostOperation
from pypokerlost.types.pokerlost_scope import PokerlostScope

if TYPE_CHECKING:
    from pypokerlost.client import PokerlostClient


class PokerlostMethod[ResultT](PokerlostType):
    """Strict request payload fields and immutable operation metadata."""

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    operation: ClassVar[PokerlostOperation]
    required_scopes: ClassVar[tuple[PokerlostScope, ...]] = ()
    returning: ClassVar[object]

    async def emit(self, client: PokerlostClient) -> ResultT:
        try:
            return await client(self)
        finally:
            self = cast("PokerlostMethod[ResultT]", None)
            client = cast("PokerlostClient", None)

    def __await__(self) -> Generator[object, None, ResultT]:
        return self.emit(self.resolve_client()).__await__()
