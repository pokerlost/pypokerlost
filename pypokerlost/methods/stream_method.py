from typing import Any

from pypokerlost.methods.base_method import BaseMethod


class StreamMethod(BaseMethod):
    """Immutable description of an explicitly managed streaming RPC operation."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        if "operation" not in cls.__dict__:
            return
        cls._validate_method_class()
