"""Canonical verified authorization context."""

from __future__ import annotations

from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    model_validator,
)

from pypokerlost.types import OAuthScope

from .enums import PrincipalType

_OAUTH_SCOPE_ADAPTER: TypeAdapter[OAuthScope] = TypeAdapter(
    OAuthScope,
    config=ConfigDict(strict=True),
)


def _validate_scopes(value: Any, info: ValidationInfo) -> tuple[OAuthScope, ...]:
    immutable_python_input = isinstance(value, (tuple, frozenset))
    json_array_input = info.mode == "json" and isinstance(value, list)
    if not immutable_python_input and not json_array_input:
        raise ValueError("Authorization scopes must be an immutable tuple or frozenset")
    try:
        scopes = tuple(_OAUTH_SCOPE_ADAPTER.validate_python(scope) for scope in value)
    except ValidationError as error:
        raise ValueError("Authorization context contains an invalid scope") from error
    if len(frozenset(scopes)) != len(scopes):
        raise ValueError("Authorization context must not contain duplicate scopes")
    return tuple(sorted(scopes))


class AuthorizationContext(BaseModel):
    """Identity and exact scopes produced by a service-owned verification adapter."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    principal_id: UUID
    principal_type: PrincipalType
    client_id: UUID
    audience: Annotated[
        str,
        StringConstraints(strict=True, min_length=1),
    ]
    scopes: Annotated[
        tuple[OAuthScope, ...],
        BeforeValidator(_validate_scopes),
    ]
    account_id: UUID | None = None
    session_id: UUID | None = None
    service_slug: (
        Annotated[
            str,
            StringConstraints(strict=True, min_length=1),
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_principal_shape(self) -> Self:
        """Keep human and service identity bindings mutually exclusive."""
        if self.principal_type is PrincipalType.HUMAN:
            if self.account_id is None or self.session_id is None:
                raise ValueError("Human authorization context requires account_id and session_id")
            if self.service_slug is not None:
                raise ValueError("Human authorization context cannot contain service_slug")
        elif self.principal_type is PrincipalType.SERVICE:
            if self.service_slug is None:
                raise ValueError("Service authorization context requires service_slug")
            if self.account_id is not None or self.session_id is not None:
                raise ValueError(
                    "Service authorization context cannot contain account_id or session_id"
                )
        return self
