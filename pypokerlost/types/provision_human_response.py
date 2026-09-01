"""Result for the future-facing provisionHuman operation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .principal_status import PrincipalStatus


class ProvisionHumanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    principal_id: UUID
    status: PrincipalStatus
