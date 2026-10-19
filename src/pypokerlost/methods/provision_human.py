"""Typed future-facing provisionHuman Pokerlost method."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import BeforeValidator

from pypokerlost.enums import PokerlostScopes
from pypokerlost.types import PokerlostOperation, ProvisionHumanResponse
from pypokerlost.types._scope_set import parse_scope_set

from .base import PokerlostMethod


def _parse_initial_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Initial scopes", allow_empty=True)


class ProvisionHuman(PokerlostMethod[ProvisionHumanResponse]):
    """Call provisionHuman when authService implements the endpoint."""

    operation = PokerlostOperation("provisionHuman")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = (
        PokerlostScopes.AUTH_INTERNAL_PROVISION_HUMAN,
    )
    returning = ProvisionHumanResponse

    business_operation_id: UUID
    account_id: UUID
    initial_scopes: Annotated[
        tuple[PokerlostScopes, ...],
        BeforeValidator(_parse_initial_scopes),
    ]
