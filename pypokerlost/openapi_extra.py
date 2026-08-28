"""PokerLost-specific non-security OpenAPI metadata."""

from __future__ import annotations

from typing import Annotated

from pydantic import ConfigDict, Field

from pypokerlost.types import JSONValue, PokerlostType

type _ContractVersion = Annotated[int, Field(strict=True, ge=1)]


class OpenAPIExtra(PokerlostType):
    """Build optional PokerLost metadata without authorization policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    contract_version: _ContractVersion = 1

    def as_dict(self) -> dict[str, JSONValue]:
        """Return a fresh OpenAPI extension mapping."""
        return {
            "x-pokerlost": {
                "contract_version": self.contract_version,
            },
        }
