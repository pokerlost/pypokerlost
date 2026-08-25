from __future__ import annotations

import re
from abc import ABC
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from pypokerlost.types import HttpMethod

_OPERATION_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class BaseMethod(BaseModel, ABC):
    """Shared immutable metadata and request fields for SDK operations."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    operation: ClassVar[str]
    http_method: ClassVar[HttpMethod] = HttpMethod.POST

    def model_post_init(self, context: Any, /) -> None:
        del context
        type(self)._validate_method_class()

    @classmethod
    def _validate_method_class(cls) -> None:
        for name, field in cls.model_fields.items():
            if _FIELD_NAME_PATTERN.fullmatch(name) is None:
                msg = f"Method field {name!r} must use snake_case"
                raise TypeError(msg)
            aliases = (field.alias, field.validation_alias, field.serialization_alias)
            if any(alias not in (None, name) for alias in aliases):
                msg = f"Method field {name!r} must not define an alias"
                raise TypeError(msg)

        operation = getattr(cls, "operation", None)
        if not isinstance(operation, str):
            msg = "Concrete methods must declare an operation"
            raise TypeError(msg)
        if _OPERATION_PATTERN.fullmatch(operation) is None:
            msg = "RPC operation must use the 'namespace.method' form"
            raise TypeError(msg)

        if not isinstance(cls.http_method, HttpMethod):
            msg = "Method http_method must be an HttpMethod value"
            raise TypeError(msg)
