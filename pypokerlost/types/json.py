"""Strict JSON-compatible value and codec types."""

from __future__ import annotations

from typing import Annotated, cast

from pydantic import BeforeValidator, FiniteFloat

type JSONScalar = bool | int | FiniteFloat | str | None


def _ensure_exact_json_value(value: object) -> object:
    value_type = type(value)
    if value is None or value_type in (bool, int, float, str, list):
        return value
    if value_type is dict:
        mapping = cast("dict[object, object]", value)
        if all(type(key) is str for key in mapping):
            return value
    raise ValueError("Value must use exact JSON-compatible built-in types")


type JSONValue = Annotated[
    JSONScalar | list[JSONValue] | dict[str, JSONValue],
    BeforeValidator(_ensure_exact_json_value),
]
