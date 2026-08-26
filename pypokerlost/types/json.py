from collections.abc import Callable
from typing import Any

type JSONDumps = Callable[..., str]
type JSONLoads = Callable[..., Any]

type JsonScalar = bool | int | float | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
