from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel

from pypokerlost.types import JsonValue


class RequestValuePreparer:
    """Copy a value into a strictly JSON-compatible tree."""

    def prepare_value(self, value: Any) -> JsonValue:
        if isinstance(value, Enum):
            return self.prepare_value(value.value)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value
        if isinstance(value, str):
            return value
        if isinstance(value, BaseModel):
            dumped = value.model_dump(mode="json", by_alias=False, exclude_unset=True)
            return self.prepare_value(dumped)
        if isinstance(value, Mapping):
            prepared: dict[str, JsonValue] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("Request mappings must use string keys")
                prepared[key] = self.prepare_value(item)
            return prepared
        if isinstance(value, (list, tuple)):
            return [self.prepare_value(item) for item in value]
        raise TypeError(f"Unsupported request value type: {type(value).__qualname__}")
