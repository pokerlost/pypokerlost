"""Payload for the future-facing provisionHuman operation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .authorization_role import AuthorizationRole


class ProvisionHumanRequest(BaseModel):
    """Idempotently provision the authorization principal for one account."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
    )

    business_operation_id: UUID
    account_id: UUID
    role: AuthorizationRole
