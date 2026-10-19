"""Payload for the future-facing replacePrincipalScopes operation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict

from pypokerlost.enums import PokerlostScopes

from ._scope_set import parse_scope_set


def _parse_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Principal scopes", allow_empty=True)


class ReplacePrincipalScopesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    business_operation_id: UUID
    principal_id: UUID
    scopes: Annotated[tuple[PokerlostScopes, ...], BeforeValidator(_parse_scopes)]
