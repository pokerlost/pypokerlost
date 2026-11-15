"""Immutable per-call Pokerlost client options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypokerlost.middleware.retry import PokerlostRetryPolicy


@dataclass(frozen=True, slots=True)
class PokerlostRequestOptions:
    """Select retry bounds and explicitly attest that replay is safe."""

    retry_policy: PokerlostRetryPolicy | None = None
    retry_safe: bool = False

    def __post_init__(self) -> None:
        if type(self.retry_safe) is not bool:
            raise TypeError("retry_safe must be a bool")
        if self.retry_policy is not None:
            from pypokerlost.middleware.retry import PokerlostRetryPolicy

            if not isinstance(self.retry_policy, PokerlostRetryPolicy):
                raise TypeError("retry_policy must be PokerlostRetryPolicy or None")
