"""Base models for typed PokerLost API objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, PrivateAttr

from pypokerlost.client.current_client import get_current_client

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


class PokerlostType(BaseModel):
    """Immutable typed PokerLost API object with optional client context."""

    model_config = ConfigDict(
        use_enum_values=True,
        extra="allow",
        validate_assignment=True,
        frozen=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        defer_build=True,
        protected_namespaces=(),
        hide_input_in_errors=True,
        validate_default=True,
        allow_inf_nan=False,
    )

    _client: Client | None = PrivateAttr(default=None)

    def model_post_init(self, context: Any, /) -> None:
        """Bind an optional client supplied through Pydantic validation context."""
        if isinstance(context, dict):
            self._client = context.get("client")

    def as_(self, client: Client | None) -> Self:
        """Bind an explicit client and return this object."""
        self._client = client
        return self

    def resolve_client(self) -> Client:
        """Return the explicit client or the task-local current client."""
        if self._client is not None:
            return self._client
        return get_current_client()

    @property
    def client(self) -> Client | None:
        """Return the explicitly/context-bound client when present."""
        return self._client


class MutablePokerlostType(PokerlostType):
    """Mutable typed PokerLost API object."""

    model_config = ConfigDict(
        frozen=False,
    )
