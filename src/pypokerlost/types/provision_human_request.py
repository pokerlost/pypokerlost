"""Payload for the future-facing provisionHuman operation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict

from pypokerlost.enums import PokerlostScopes

from ._scope_set import parse_scope_set


def _parse_initial_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Initial scopes", allow_empty=True)


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
    initial_scopes: Annotated[
        tuple[PokerlostScopes, ...],
        BeforeValidator(_parse_initial_scopes),
    ]
