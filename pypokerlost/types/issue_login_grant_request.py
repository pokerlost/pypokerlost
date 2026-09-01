"""Payload for the future-facing issueLoginGrant operation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IssueLoginGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    business_operation_id: UUID
    principal_id: UUID
