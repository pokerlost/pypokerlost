"""Payload for the future-facing assignPrincipalRole operation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .authorization_role import AuthorizationRole


class AssignPrincipalRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    business_operation_id: UUID
    principal_id: UUID
    role: AuthorizationRole
