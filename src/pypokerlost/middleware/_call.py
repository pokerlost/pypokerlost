"""Private immutable state for one SDK execution."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from pydantic import SecretStr

if TYPE_CHECKING:
    from pypokerlost.client.pokerlost_request_options import PokerlostRequestOptions
    from pypokerlost.enums import PokerlostScopes
    from pypokerlost.methods import PokerlostMethod
    from pypokerlost.types import PokerlostRequest


_refresh_claimed: ContextVar[bool | None] = ContextVar(
    "pokerlost_reactive_refresh_claimed",
    default=None,
)


@contextmanager
def reactive_refresh_scope() -> Iterator[None]:
    """Share one refresh allowance across every attempt in a logical call."""
    token = _refresh_claimed.set(False)
    try:
        yield
    finally:
        _refresh_claimed.reset(token)


def claim_reactive_refresh() -> bool:
    """Atomically claim the task-local one-refresh allowance."""
    claimed = _refresh_claimed.get()
    if claimed is None:
        raise RuntimeError("Reactive refresh scope is not initialized")
    if claimed:
        return False
    _refresh_claimed.set(True)
    return True


@dataclass(frozen=True, slots=True)
class PokerlostCall:
    """Keep wire data separate from private execution and authentication state."""

    method: PokerlostMethod[object]
    request: PokerlostRequest[object]
    options: PokerlostRequestOptions
    scopes: tuple[PokerlostScopes, ...] | None
    access_token: SecretStr | None = None

    def with_access_token(self, token: str, /) -> PokerlostCall:
        return replace(self, access_token=SecretStr(token))
