"""Base models for typed Pokerlost API objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, PrivateAttr

if TYPE_CHECKING:
    from pypokerlost.client import PokerlostClient


class PokerlostType(BaseModel):
    """Immutable typed Pokerlost API object with optional client context."""

    model_config = ConfigDict(
        use_enum_values=True,
        extra="forbid",
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

    _client: PokerlostClient | None = PrivateAttr(default=None)

    def model_post_init(self, context: object, /) -> None:
        """Bind an optional client supplied through Pydantic validation context."""
        if isinstance(context, dict):
            candidate: object = context.get("client")
            from pypokerlost.client import PokerlostClient

            if isinstance(candidate, PokerlostClient):
                self._client = candidate

    def as_(self, client: PokerlostClient | None) -> Self:
        """Bind an explicit client and return this object."""
        self._client = client
        return self

    def resolve_client(self) -> PokerlostClient:
        """Return the explicit client or the task-local current client."""
        if self._client is not None:
            return self._client
        from pypokerlost.client.current_client import get_current_client

        return get_current_client()

    @property
    def client(self) -> PokerlostClient | None:
        """Return the explicitly/context-bound client when present."""
        return self._client


class MutablePokerlostType(PokerlostType):
    """Mutable typed Pokerlost API object."""

    model_config = ConfigDict(
        frozen=False,
    )
