"""Base models for typed Pokerlost API objects."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PokerlostType(BaseModel):
    """Immutable typed Pokerlost API object."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        frozen=True,
        populate_by_name=True,
        defer_build=True,
        protected_namespaces=(),
        hide_input_in_errors=True,
        validate_default=True,
        allow_inf_nan=False,
    )


class MutablePokerlostType(PokerlostType):
    """Mutable typed Pokerlost API object."""

    model_config = ConfigDict(
        frozen=False,
    )
