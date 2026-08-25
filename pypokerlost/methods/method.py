from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, ClassVar, cast

from pydantic import BaseModel, ConfigDict

from pypokerlost.client.current_client import get_current_client
from pypokerlost.transport import TransportRequest, TransportResponse
from pypokerlost.types import JsonValue

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


_OPERATION_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


def _validate_operation(operation: str) -> None:
    if _OPERATION_PATTERN.fullmatch(operation) is None:
        msg = "RPC operation must use the 'namespace.method' form"
        raise TypeError(msg)


def _validate_method_class(method_class: type[BaseModel]) -> None:
    for name, field in method_class.model_fields.items():
        if _FIELD_NAME_PATTERN.fullmatch(name) is None:
            msg = f"Method field {name!r} must use snake_case"
            raise TypeError(msg)
        aliases = (field.alias, field.validation_alias, field.serialization_alias)
        if any(alias not in (None, name) for alias in aliases):
            msg = f"Method field {name!r} must not define an alias"
            raise TypeError(msg)

    if not inspect.isabstract(method_class):
        operation = getattr(method_class, "operation", None)
        if not isinstance(operation, str):
            msg = "Concrete methods must declare an operation"
            raise TypeError(msg)
        _validate_operation(operation)


def _build_rpc_request(model: BaseModel, operation: str) -> TransportRequest:
    _validate_operation(operation)
    payload = cast(JsonValue, model.model_dump(mode="json", by_alias=False))
    return TransportRequest(method="POST", path=f"/{operation}", json=payload)


class Method[ResultT](BaseModel, ABC):
    """Immutable request model for an ordinary typed RPC operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    operation: ClassVar[str]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        _validate_method_class(cls)

    def build_request(self) -> TransportRequest:
        """Build the default JSON-over-HTTP RPC request."""
        return _build_rpc_request(self, self.operation)

    @abstractmethod
    def parse_response(self, response: TransportResponse) -> ResultT:
        """Decode a successful transport response into the declared result type."""

    async def execute(self, client: Client | None = None) -> ResultT:
        """Execute through an explicit client or the task-local current client."""
        resolved_client = client if client is not None else get_current_client()
        return await resolved_client.make_request(self)

    def __await__(self) -> Generator[Any, None, ResultT]:
        return self.execute().__await__()
