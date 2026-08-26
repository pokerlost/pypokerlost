from __future__ import annotations

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
    client = _current_client.get()
    if client is None:
        raise ClientContextError
    return client


def set_current_client(client: Client) -> Token[Client | None]:
    return _current_client.set(client)


def reset_current_client(token: Token[Client | None]) -> None:
    _current_client.reset(token)
