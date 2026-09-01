"""Typed future-facing provisionHuman Pokerlost method."""

from __future__ import annotations

from uuid import UUID

from pypokerlost.types import (
    AuthorizationRole,
    PokerlostOperation,
    PokerlostScope,
    ProvisionHumanResponse,
)

from .base import PokerlostMethod


class ProvisionHuman(PokerlostMethod[ProvisionHumanResponse]):
    """Call provisionHuman when authService implements the endpoint."""

    operation = PokerlostOperation("provisionHuman")
    required_scopes = (PokerlostScope("auth.internal.provisionHuman"),)
    returning = ProvisionHumanResponse

    business_operation_id: UUID
    account_id: UUID
    role: AuthorizationRole
