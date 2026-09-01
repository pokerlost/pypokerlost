"""Canonical OAuth2 scope identifiers and scope-string conversion."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from pydantic import ConfigDict, StringConstraints, TypeAdapter, ValidationError

type OAuthScope = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[a-z][A-Za-z0-9]*(\.[a-z][A-Za-z0-9]*)+$",
    ),
]

_OAUTH_SCOPE_ADAPTER: TypeAdapter[OAuthScope] = TypeAdapter(
    OAuthScope,
    config=ConfigDict(strict=True),
)


def parse_oauth_scope_string(value: str, /) -> tuple[OAuthScope, ...]:
    """Parse a non-empty OAuth2 scope string into canonical sorted scopes."""
    if not isinstance(value, str):
        raise TypeError("OAuth2 scope string must be a str")

    raw_scopes = value.split(" ")
    if not value or any(not scope for scope in raw_scopes):
        raise ValueError("OAuth2 scope string must contain non-empty space-delimited scopes")

    try:
        scopes = tuple(_OAUTH_SCOPE_ADAPTER.validate_python(scope) for scope in raw_scopes)
    except ValidationError as error:
        raise ValueError("OAuth2 scope string contains an invalid scope") from error

    if len(frozenset(scopes)) != len(scopes):
        raise ValueError("OAuth2 scope string must not contain duplicate scopes")
    return tuple(sorted(scopes))


def format_oauth_scope_string(scopes: Iterable[OAuthScope], /) -> str:
    """Validate scopes and return their canonical sorted OAuth2 scope string."""
    if isinstance(scopes, str):
        raise TypeError("OAuth2 scopes must be an iterable of scope strings")
    try:
        parsed = tuple(_OAUTH_SCOPE_ADAPTER.validate_python(scope) for scope in scopes)
    except TypeError:
        raise TypeError("OAuth2 scopes must be an iterable of scope strings") from None
    except ValidationError as error:
        raise ValueError("OAuth2 scopes contain an invalid scope") from error

    if not parsed:
        raise ValueError("OAuth2 scopes must not be empty")
    if len(frozenset(parsed)) != len(parsed):
        raise ValueError("OAuth2 scopes must not contain duplicates")
    return " ".join(sorted(parsed))
