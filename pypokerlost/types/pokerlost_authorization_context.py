"""Canonical verified Pokerlost authorization context."""

from __future__ import annotations

from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StringConstraints,
    model_validator,
)

from .pokerlost_scope import PokerlostScope, canonicalize_pokerlost_scopes
from .principal_type import PrincipalType


def _canonical_scopes(value: object) -> tuple[PokerlostScope, ...]:
    if not isinstance(value, (list, tuple, frozenset)):
        raise ValueError("Authorization scopes must be a tuple or JSON array")
    return canonicalize_pokerlost_scopes(value)


class PokerlostAuthorizationContext(BaseModel):
    """Identity, audience, and exact scopes returned by a local verifier."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    principal_id: UUID
    principal_type: PrincipalType
    client_id: UUID
    audience: Annotated[str, StringConstraints(strict=True, min_length=1)]
    scopes: Annotated[
        tuple[PokerlostScope, ...],
        BeforeValidator(_canonical_scopes),
    ]
    account_id: UUID | None = None
    session_id: UUID | None = None
    service_slug: Annotated[str, StringConstraints(strict=True, min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_principal_shape(self) -> Self:
        """Keep human and service identity bindings mutually exclusive."""
        if self.principal_type is PrincipalType.HUMAN:
            if self.account_id is None or self.session_id is None:
                raise ValueError("Human authorization requires account_id and session_id")
            if self.service_slug is not None:
                raise ValueError("Human authorization cannot contain service_slug")
        elif self.principal_type is PrincipalType.SERVICE:
            if self.service_slug is None:
                raise ValueError("Service authorization requires service_slug")
            if self.account_id is not None or self.session_id is not None:
                raise ValueError("Service authorization cannot contain human bindings")
        return self
