"""Protected Pokerlost JSON request envelope."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from .pokerlost_authorization import PokerlostAuthorization

if TYPE_CHECKING:
    from pypokerlost.client import PokerlostRequestOptions
    from pypokerlost.methods import PokerlostMethod


class PokerlostAuthorizedRequest[PayloadT](BaseModel):
    """The only envelope for a protected Pokerlost operation payload."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    authorization: PokerlostAuthorization = Field(repr=False)
    payload: PayloadT
    _method: PokerlostMethod[object] | None = PrivateAttr(default=None)
    _options: PokerlostRequestOptions | None = PrivateAttr(default=None)

    @property
    def method(self) -> PokerlostMethod[object]:
        """Return private call metadata that is never serialized."""
        if self._method is None:
            raise ValueError("Pokerlost request is not bound to a method")
        return self._method

    @property
    def options(self) -> PokerlostRequestOptions:
        """Return private per-call options that are never serialized."""
        if self._options is None:
            raise ValueError("Pokerlost request is not bound to call options")
        return self._options

    def bind_call(
        self,
        method: PokerlostMethod[object],
        options: PokerlostRequestOptions,
        /,
    ) -> PokerlostAuthorizedRequest[PayloadT]:
        """Return a copy carrying non-wire method and option metadata."""
        request = self.model_copy(deep=False)
        request._method = method
        request._options = options
        return request
