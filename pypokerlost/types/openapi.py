from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field

from .non_empty_string import NonEmptyString

type OpenAPIContractVersion = Annotated[int, Field(strict=True, ge=1)]
type OpenAPISecurityScheme = NonEmptyString
type OAuth2Scope = NonEmptyString


def _ensure_unique_oauth2_scopes(
    scopes: tuple[OAuth2Scope, ...],
) -> tuple[OAuth2Scope, ...]:
    if len(scopes) != len(set(scopes)):
        raise ValueError("OAuth2 scopes must not contain duplicates")
    return scopes


type OAuth2Scopes = Annotated[
    tuple[OAuth2Scope, ...],
    AfterValidator(_ensure_unique_oauth2_scopes),
]
