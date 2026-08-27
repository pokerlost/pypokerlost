from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, PrivateAttr

from pypokerlost.client.current_client import get_current_client

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class ClientContextController(BaseModel):
    """Store an explicitly bound client outside a model's wire fields."""

    _client: Client | None = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        context_client = __context.get("client") if __context else None
        self._client = context_client

    def as_(self, client: Client | None) -> Self:
        self._client = client
        return self

    def resolve_client(self) -> Client:
        if self._client is not None:
            return self._client
        return get_current_client()

    @property
    def client(self) -> Client | None:
        return self._client
