from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from pydantic import TypeAdapter, ValidationError

from pypokerlost.contracts import ApplicationResponse
from pypokerlost.exceptions import ApplicationError, ResponseDecodeError
from pypokerlost.methods import Method
from pypokerlost.types import JsonValue


@dataclass(frozen=True, slots=True)
class RawResponse:
    """Buffered response independent of a concrete HTTP implementation."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


_ENVELOPE_ADAPTER = TypeAdapter(ApplicationResponse[JsonValue])


def _result_adapter[ResultT](method_type: type[Method[ResultT]]) -> TypeAdapter[ResultT]:
    try:
        returning = method_type.__returning__
    except AttributeError:
        raise TypeError("Concrete ordinary methods must declare __returning__") from None
    return cast(TypeAdapter[ResultT], TypeAdapter(returning))


class ResponseHandler:
    """Decode the shared envelope declared by an ordinary method."""

    def handle[ResultT](
        self,
        method: Method[ResultT],
        operation: str,
        response: RawResponse,
    ) -> ResultT:
        try:
            envelope = _ENVELOPE_ADAPTER.validate_json(response.body)
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

        try:
            return _result_adapter(type(method)).validate_python(envelope.result)
        except ValidationError:
            raise ResponseDecodeError(
                operation=operation,
                status_code=response.status_code,
            ) from None
