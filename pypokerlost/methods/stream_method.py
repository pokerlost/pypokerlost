from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict

from pypokerlost.methods.method import _build_rpc_request, _validate_method_class
from pypokerlost.transport import TransportRequest


class StreamMethod(BaseModel, ABC):
    """Immutable request model for an explicitly managed streaming RPC operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @property
    @abstractmethod
    def operation(self) -> str:
        """Stable RPC operation overridden by each concrete class-level value."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        _validate_method_class(cls)

    def build_request(self) -> TransportRequest:
        """Build the default JSON-over-HTTP RPC request."""
        return _build_rpc_request(self, self.operation)
