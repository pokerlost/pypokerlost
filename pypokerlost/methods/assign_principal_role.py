"""Typed future-facing assignPrincipalRole Pokerlost method."""

from __future__ import annotations

from uuid import UUID

from pypokerlost.types import (
    AssignPrincipalRoleResponse,
    AuthorizationRole,
    PokerlostOperation,
    PokerlostScope,
)

from .base import PokerlostMethod


class AssignPrincipalRole(PokerlostMethod[AssignPrincipalRoleResponse]):
    """Call assignPrincipalRole when authService implements the endpoint."""

    operation = PokerlostOperation("assignPrincipalRole")
    required_scopes = (PokerlostScope("auth.internal.assignPrincipalRole"),)
    returning = AssignPrincipalRoleResponse

    business_operation_id: UUID
    principal_id: UUID
    role: AuthorizationRole
