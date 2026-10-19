"""Task-local Pokerlost client context."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from pypokerlost.errors import PokerlostConfigurationError

if TYPE_CHECKING:
    from .client import PokerlostClient

_current_client: ContextVar[PokerlostClient | None] = ContextVar(
    "pypokerlost_current_client",
    default=None,
)


def get_current_client() -> PokerlostClient:
    client = _current_client.get()
    if client is None:
        raise PokerlostConfigurationError("No PokerlostClient is active in this task")
    return client


@contextmanager
def use_current_client(client: PokerlostClient) -> Iterator[PokerlostClient]:
    token: Token[PokerlostClient | None] = _current_client.set(client)
    try:
        yield client
    finally:
        _current_client.reset(token)
