"""Canonical verified Pokerlost authorization context."""

from __future__ import annotations

from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints, model_validator

from pypokerlost.enums import PokerlostScopes, PrincipalType

from ._scope_set import parse_scope_set
from .pokerlost_audience import PokerlostAudience


def _parse_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Authorization scopes")


class PokerlostAuthorizationContext(BaseModel):
    """Role-free identity, exact audience, and scopes returned by a verifier."""

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
    audience: PokerlostAudience
    scopes: Annotated[tuple[PokerlostScopes, ...], BeforeValidator(_parse_scopes)]
    account_id: UUID | None = None
    session_id: UUID | None = None
    service_name: Annotated[str, StringConstraints(strict=True, min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_principal_shape(self) -> Self:
        if self.principal_type is PrincipalType.HUMAN and self.service_name is not None:
            raise ValueError("Human authorization cannot contain service_name")
        if self.principal_type is PrincipalType.SERVICE and (
            self.account_id is not None or self.session_id is not None
        ):
            raise ValueError("Service authorization cannot contain human bindings")
        return self
