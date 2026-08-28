"""Task-local current-client state."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from pypokerlost.exceptions import ClientContextError

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


_current_client: ContextVar[Client | None] = ContextVar(
    "pypokerlost_current_client",
    default=None,
)


def get_current_client() -> Client:
    """Return the client installed in the current task context."""
    client = _current_client.get()
    if client is None:
        raise ClientContextError
    return client


@contextmanager
def use_current_client(client: Client) -> Iterator[Client]:
    """Install a client temporarily and restore the exact previous context."""
    token: Token[Client | None] = _current_client.set(client)
    try:
        yield client
    finally:
        _current_client.reset(token)
