from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, PrivateAttr

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class ClientContextController(BaseModel):
    """Store an explicitly bound client outside a model's wire fields."""

    _client: Client | None = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        context_client = __context.get("client") if __context else None
        self._client = context_client

    def as_(self, client: Client) -> Self:
        self._client = client
        return self

    @property
    def client(self) -> Client | None:
        return self._client
