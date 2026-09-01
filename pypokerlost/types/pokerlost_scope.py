"""Validated Pokerlost scope identifiers and canonical scope helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

_SCOPE_PATTERN = re.compile(r"^[a-z][A-Za-z0-9]*(\.[a-z][A-Za-z0-9]*)+$")


class PokerlostScope(str):
    """A dotted Pokerlost scope whose segments use lowerCamelCase."""

    def __new__(cls, value: str) -> PokerlostScope:
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise TypeError("Pokerlost scope must be a str")
        normalized = str(value)
        if _SCOPE_PATTERN.fullmatch(normalized) is None:
            raise ValueError("Pokerlost scope must contain lowerCamelCase dotted segments")
        return str.__new__(cls, normalized)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        del source_type, handler
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(strict=True),
        )


def canonicalize_pokerlost_scopes(
    scopes: Iterable[PokerlostScope | str],
    /,
) -> tuple[PokerlostScope, ...]:
    """Return a sorted, duplicate-free immutable scope tuple."""
    if isinstance(scopes, str):
        raise TypeError("Pokerlost scopes must be an iterable of scope strings")
    try:
        parsed = tuple(PokerlostScope(scope) for scope in scopes)
    except TypeError:
        raise TypeError("Pokerlost scopes must be an iterable of scope strings") from None
    if len(frozenset(parsed)) != len(parsed):
        raise ValueError("Pokerlost scopes must not contain duplicates")
    return tuple(sorted(parsed))


def parse_pokerlost_scope_string(value: str, /) -> tuple[PokerlostScope, ...]:
    """Parse an internal space-delimited claim value into exact scopes."""
    if type(value) is not str:
        raise TypeError("Pokerlost scope string must be a str")
    raw_scopes = value.split(" ")
    if not value or any(not scope for scope in raw_scopes):
        raise ValueError("Pokerlost scope string must contain non-empty scopes")
    return canonicalize_pokerlost_scopes(raw_scopes)


def format_pokerlost_scope_string(
    scopes: Iterable[PokerlostScope | str],
    /,
) -> str:
    """Format exact scopes for the internal access-token claim representation."""
    canonical = canonicalize_pokerlost_scopes(scopes)
    if not canonical:
        raise ValueError("Pokerlost scopes must not be empty")
    return " ".join(canonical)
