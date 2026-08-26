from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from pydantic import TypeAdapter, ValidationError

from pypokerlost.contracts import ApplicationResponse
from pypokerlost.exceptions import ApplicationError, ResponseDecodeError
from pypokerlost.methods import BaseMethod, Method

if TYPE_CHECKING:
    from pypokerlost.client.client import Client


@dataclass(frozen=True, slots=True)
class RawResponse:
    """Buffered response independent of a concrete HTTP implementation."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@cache
def _response_adapter(method_type: type[BaseMethod]) -> TypeAdapter[ApplicationResponse[Any]]:
    returning = getattr(method_type, "__returning__", None)
    if returning is None:
        raise TypeError("Concrete ordinary methods must declare __returning__")
    # Pydantic accepts runtime annotations here; mypy requires a static type expression.
    response_type = ApplicationResponse[returning]  # type: ignore[valid-type]
    return TypeAdapter(response_type)


@cache
def _cached_result_adapter(method_type: type[BaseMethod]) -> TypeAdapter[Any]:
    returning = getattr(method_type, "__returning__", None)
    if returning is None:
        raise TypeError("Concrete ordinary methods must declare __returning__")
    return TypeAdapter(returning)


def _result_adapter[ResultT](method_type: type[Method[ResultT]]) -> TypeAdapter[ResultT]:
    return cast(TypeAdapter[ResultT], _cached_result_adapter(method_type))


class ResponseHandler:
    """Decode the shared envelope declared by an ordinary method."""

    def handle[ResultT](
        self,
        client: Client,
        method: Method[ResultT],
        response: RawResponse,
    ) -> ResultT:
        operation = _operation(method)
        try:
            envelope = _response_adapter(type(method)).validate_json(response.body)
        except ValidationError:
            raise ResponseDecodeError(
                operation=operation,
                status_code=response.status_code,
            ) from None

        if not envelope.ok:
            if envelope.error is None or envelope.error_message is None:
                raise ResponseDecodeError(
                    operation=operation,
                    status_code=response.status_code,
                )
            raise ApplicationError(
                error=envelope.error,
                error_message=envelope.error_message,
                operation=operation,
                status_code=response.status_code,
            )

        if envelope.result is None:
            try:
                return _result_adapter(type(method)).validate_python(None)
            except ValidationError:
                raise ResponseDecodeError(
                    operation=operation,
                    status_code=response.status_code,
                ) from None

        # The specialized ApplicationResponse has already validated a non-null result.
        return cast(ResultT, envelope.result)


def _operation(method: BaseMethod) -> str:
    operation = getattr(type(method), "__api_method__", None)
    if not isinstance(operation, str) or not operation.strip():
        raise TypeError("Concrete methods must declare a non-empty __api_method__")
    return operation
