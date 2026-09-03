"""Typed future-facing issueLoginGrant Pokerlost method."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pypokerlost.enums import PokerlostScopes
from pypokerlost.types import IssueLoginGrantResponse, PokerlostOperation

from .base import PokerlostMethod


class IssueLoginGrant(PokerlostMethod[IssueLoginGrantResponse]):
    """Call issueLoginGrant when authService implements the endpoint."""

    operation = PokerlostOperation("issueLoginGrant")
    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = (
        PokerlostScopes.AUTH_INTERNAL_ISSUE_LOGIN_GRANT,
    )
    returning = IssueLoginGrantResponse

    business_operation_id: UUID
    principal_id: UUID
