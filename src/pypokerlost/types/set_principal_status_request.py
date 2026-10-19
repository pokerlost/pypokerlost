"""Payload for the future-facing setPrincipalStatus operation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from pypokerlost.enums import PrincipalStatus


class SetPrincipalStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    business_operation_id: UUID
    principal_id: UUID
    status: PrincipalStatus
