"""Typed future-facing setPrincipalStatus Pokerlost method."""

from __future__ import annotations

from uuid import UUID

from pypokerlost.types import (
    PokerlostOperation,
    PokerlostScope,
    PrincipalStatus,
    SetPrincipalStatusResponse,
)

from .base import PokerlostMethod


class SetPrincipalStatus(PokerlostMethod[SetPrincipalStatusResponse]):
    """Call setPrincipalStatus when authService implements the endpoint."""

    operation = PokerlostOperation("setPrincipalStatus")
    required_scopes = (PokerlostScope("auth.internal.setPrincipalStatus"),)
    returning = SetPrincipalStatusResponse

    business_operation_id: UUID
    principal_id: UUID
    status: PrincipalStatus
