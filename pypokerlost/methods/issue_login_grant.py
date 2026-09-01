"""Typed future-facing issueLoginGrant Pokerlost method."""

from __future__ import annotations

from uuid import UUID

from pypokerlost.types import (
    IssueLoginGrantResponse,
    PokerlostOperation,
    PokerlostScope,
)

from .base import PokerlostMethod


class IssueLoginGrant(PokerlostMethod[IssueLoginGrantResponse]):
    """Call issueLoginGrant when authService implements the endpoint."""

    operation = PokerlostOperation("issueLoginGrant")
    required_scopes = (PokerlostScope("auth.internal.issueLoginGrant"),)
    returning = IssueLoginGrantResponse

    business_operation_id: UUID
    principal_id: UUID
