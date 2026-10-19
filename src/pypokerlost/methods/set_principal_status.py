"""Typed future-facing setPrincipalStatus Pokerlost method."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pypokerlost.enums import PokerlostScopes, PrincipalStatus
from pypokerlost.types import PokerlostOperation, SetPrincipalStatusResponse

from .base import PokerlostMethod


class SetPrincipalStatus(PokerlostMethod[SetPrincipalStatusResponse]):
    """Call setPrincipalStatus when authService implements the endpoint."""

    operation = PokerlostOperation("setPrincipalStatus")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = (
        PokerlostScopes.AUTH_INTERNAL_SET_PRINCIPAL_STATUS,
    )
    returning = SetPrincipalStatusResponse

    business_operation_id: UUID
    principal_id: UUID
    status: PrincipalStatus
