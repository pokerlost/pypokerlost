"""Result for the future-facing setPrincipalStatus operation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from pypokerlost.enums import PrincipalStatus


class SetPrincipalStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    principal_id: UUID
    status: PrincipalStatus
