"""Base contract for typed Pokerlost API methods."""

from __future__ import annotations

from collections.abc import Generator
from typing import ClassVar

from pydantic import ConfigDict

from pypokerlost.enums import PokerlostScopes
from pypokerlost.types.base import PokerlostType
from pypokerlost.types.pokerlost_operation import PokerlostOperation


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
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None]
    returning: ClassVar[object]

    def __await__(self) -> Generator[object, None, ResultT]:
        from pypokerlost.client.current_client import get_current_client

        return get_current_client()(self).__await__()
