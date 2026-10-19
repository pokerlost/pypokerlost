"""Immutable per-call Pokerlost client options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypokerlost.middleware.retry import PokerlostRetryPolicy


@dataclass(frozen=True, slots=True)
class PokerlostRequestOptions:
    """Opt one logical call into the canonical retry policy."""

    retry_policy: PokerlostRetryPolicy | None = None

    def __post_init__(self) -> None:
        if self.retry_policy is not None:
            from pypokerlost.middleware.retry import PokerlostRetryPolicy

            if not isinstance(self.retry_policy, PokerlostRetryPolicy):
                raise TypeError("retry_policy must be PokerlostRetryPolicy or None")
