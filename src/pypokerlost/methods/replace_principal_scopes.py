"""Typed future-facing replacePrincipalScopes Pokerlost method."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import BeforeValidator

from pypokerlost.enums import PokerlostScopes
from pypokerlost.types import PokerlostOperation, ReplacePrincipalScopesResponse
from pypokerlost.types._scope_set import parse_scope_set

from .base import PokerlostMethod


def _parse_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Principal scopes", allow_empty=True)


class ReplacePrincipalScopes(PokerlostMethod[ReplacePrincipalScopesResponse]):
    """Call replacePrincipalScopes when authService implements the endpoint."""

    operation = PokerlostOperation("replacePrincipalScopes")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = (
        PokerlostScopes.AUTH_INTERNAL_REPLACE_PRINCIPAL_SCOPES,
    )
    returning = ReplacePrincipalScopesResponse

    business_operation_id: UUID
    principal_id: UUID
    scopes: Annotated[tuple[PokerlostScopes, ...], BeforeValidator(_parse_scopes)]
