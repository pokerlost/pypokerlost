from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from pydantic import BeforeValidator, FiniteFloat

type JSONDumps = Callable[..., str]
type JSONLoads = Callable[..., Any]

type JSONScalar = bool | int | FiniteFloat | str | None


def _ensure_exact_json_value(value: Any) -> Any:
    value_type = type(value)
    if value is None or value_type in (bool, int, float, str, list):
        return value
    if value_type is dict and all(type(key) is str for key in value):
        return value
    raise ValueError("Value must use exact JSON-compatible built-in types")


type JSONValue = Annotated[
    JSONScalar | list[JSONValue] | dict[str, JSONValue],
    BeforeValidator(_ensure_exact_json_value),
]
