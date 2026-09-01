"""Canonical decoded access-token claims."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
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

from pypokerlost.types import format_oauth_scope_string, parse_oauth_scope_string

from .enums import AuthorizationRole, PrincipalType


def _canonicalize_scope_string(value: str) -> str:
    return format_oauth_scope_string(parse_oauth_scope_string(value))


def _parse_numeric_date(value: Any) -> Any:
    if type(value) is int:
        return datetime.fromtimestamp(value, tz=UTC)
    return value


def _parse_uuid(value: Any) -> Any:
    if type(value) is str:
        return UUID(value)
    return value


def _parse_principal_type(value: Any) -> Any:
    if type(value) is str:
        return PrincipalType(value)
    return value


def _parse_authorization_role(value: Any) -> Any:
    if type(value) is str:
        return AuthorizationRole(value)
    return value


class AccessTokenClaims(BaseModel):
    """Validated access-token data without signing or verification behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    issuer: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(alias="iss")
    subject: Annotated[UUID, BeforeValidator(_parse_uuid)] = Field(alias="sub")
    audience: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ] = Field(alias="aud")
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
    token_use: Literal["access"]
    client_id: Annotated[UUID, BeforeValidator(_parse_uuid)]
    scope: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
        AfterValidator(_canonicalize_scope_string),
    ]
    principal_type: Annotated[
        PrincipalType,
        BeforeValidator(_parse_principal_type),
    ]
    role: Annotated[
        AuthorizationRole,
        BeforeValidator(_parse_authorization_role),
    ]
    account_id: Annotated[UUID, BeforeValidator(_parse_uuid)] | None = None
    session_id: Annotated[UUID, BeforeValidator(_parse_uuid)] | None = None
    service_slug: (
        Annotated[
            str,
            StringConstraints(strict=True, min_length=1),
        ]
        | None
    ) = None

    @field_serializer("issued_at", "not_before", "expires_at")
    def serialize_numeric_date(self, value: datetime) -> int:
        """Serialize JWT timestamps as NumericDate values."""
        return int(value.astimezone(UTC).timestamp())

    @model_validator(mode="after")
    def validate_claim_invariants(self) -> Self:
        """Enforce temporal and principal-shape data invariants."""
        if self.expires_at <= self.not_before or self.expires_at <= self.issued_at:
            raise ValueError("Access token expiry must follow issuance and not-before times")
        if self.subject == self.client_id:
            raise ValueError("Access token subject and OAuth2 client identifiers must differ")

        if self.principal_type is PrincipalType.HUMAN:
            if self.account_id is None or self.session_id is None:
                raise ValueError("Human access token claims require account_id and session_id")
            if self.service_slug is not None:
                raise ValueError("Human access token claims cannot contain service_slug")
            if self.role is AuthorizationRole.AUTO:
                raise ValueError("Human access token claims cannot use the auto role")
        elif self.principal_type is PrincipalType.SERVICE:
            if self.service_slug is None:
                raise ValueError("Service access token claims require service_slug")
            if self.account_id is not None or self.session_id is not None:
                raise ValueError(
                    "Service access token claims cannot contain account_id or session_id"
                )
            if self.role is not AuthorizationRole.AUTO:
                raise ValueError("Service access token claims require the auto role")
        return self
