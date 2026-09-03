"""Focused validation for SDK scope sets."""

from __future__ import annotations

from pypokerlost.enums import PokerlostScopes


def parse_scope_set(
    value: object,
    /,
    *,
    field_name: str,
    allow_empty: bool = False,
) -> tuple[PokerlostScopes, ...]:
    """Return one canonical scope tuple with explicit empty-set semantics."""
    if not isinstance(value, (list, tuple, frozenset)):
        raise ValueError(f"{field_name} must be a tuple or JSON array")
    try:
        parsed = tuple(PokerlostScopes(item) for item in value)
    except TypeError, ValueError:
        raise ValueError(f"{field_name} contain an unknown Pokerlost scope") from None
    if not parsed and not allow_empty:
        raise ValueError(f"{field_name} must not be empty")
    if len(frozenset(parsed)) != len(parsed):
        raise ValueError(f"{field_name} must not contain duplicates")
    return tuple(sorted(parsed, key=lambda item: item.value))
