"""Validated Pokerlost access-token claims."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    WithJsonSchema,
    field_serializer,
    model_validator,
)

from pypokerlost.enums import PokerlostScopes, PrincipalType

from ._scope_set import parse_scope_set
from .pokerlost_audience import PokerlostAudience


def _parse_numeric_date(value: object) -> object:
    if type(value) is int:
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except OverflowError, OSError, ValueError:
            raise ValueError("JWT NumericDate is outside the supported range") from None
    return value


def _parse_uuid(value: object) -> object:
    if type(value) is str:
        return UUID(value)
    return value


def _parse_principal_type(value: object) -> object:
    if type(value) is str:
        return PrincipalType(value)
    return value


def _parse_scopes(value: object) -> tuple[PokerlostScopes, ...]:
    return parse_scope_set(value, field_name="Access-token scopes")


class PokerlostAccessTokenClaims(BaseModel):
    """JWT-compatible, role-free claim data without verification behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    issuer: Annotated[str, StringConstraints(strict=True, min_length=1)] = Field(alias="iss")
    subject: Annotated[UUID, BeforeValidator(_parse_uuid)] = Field(alias="sub")
    audience: PokerlostAudience = Field(alias="aud")
    issued_at: Annotated[
        AwareDatetime,
        BeforeValidator(_parse_numeric_date),
        WithJsonSchema({"type": "integer"}),
    ] = Field(alias="iat")
    not_before: Annotated[
        AwareDatetime,
        BeforeValidator(_parse_numeric_date),
        WithJsonSchema({"type": "integer"}),
    ] = Field(alias="nbf")
    expires_at: Annotated[
        AwareDatetime,
        BeforeValidator(_parse_numeric_date),
        WithJsonSchema({"type": "integer"}),
    ] = Field(alias="exp")
    token_id: Annotated[UUID, BeforeValidator(_parse_uuid)] = Field(alias="jti")
    client_id: Annotated[UUID, BeforeValidator(_parse_uuid)]
    scopes: Annotated[tuple[PokerlostScopes, ...], BeforeValidator(_parse_scopes)]
    principal_type: Annotated[PrincipalType, BeforeValidator(_parse_principal_type)]
    account_id: Annotated[UUID, BeforeValidator(_parse_uuid)] | None = None
    session_id: Annotated[UUID, BeforeValidator(_parse_uuid)] | None = None
    service_name: Annotated[str, StringConstraints(strict=True, min_length=1)] | None = None

    @field_serializer("issued_at", "not_before", "expires_at")
    def serialize_numeric_date(self, value: datetime) -> int:
        return int(value.astimezone(UTC).timestamp())

    @model_validator(mode="after")
    def validate_claim_invariants(self) -> Self:
        if self.expires_at <= self.not_before or self.expires_at <= self.issued_at:
            raise ValueError("Access token expiry must follow issuance and not-before times")
        if self.subject == self.client_id:
            raise ValueError("Access token subject and client identifiers must differ")
        if self.principal_type is PrincipalType.HUMAN and self.service_name is not None:
            raise ValueError("Human claims cannot contain service_name")
        if self.principal_type is PrincipalType.SERVICE and (
            self.account_id is not None or self.session_id is not None
        ):
            raise ValueError("Service claims cannot contain human bindings")
        return self
