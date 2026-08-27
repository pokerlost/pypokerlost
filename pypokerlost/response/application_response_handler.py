from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from pydantic import TypeAdapter, ValidationError

from pypokerlost.contracts import ApplicationResponse
from pypokerlost.exceptions import (
    ClientDecodeError,
    PokerlostAPIError,
    PokerlostProtocolError,
)
from pypokerlost.response.base_response_handler import BaseResponseHandler
from pypokerlost.types import JSONLoads, JSONValue

if TYPE_CHECKING:
    from pypokerlost.methods import PokerlostMethod


class ApplicationResponseHandler(BaseResponseHandler):
    """Interpret the fixed public ``ApplicationResponse`` protocol."""

    def __init__(self, json_loads: JSONLoads = json.loads) -> None:
        self._json_loads = json_loads
        self._envelope_adapter = TypeAdapter(ApplicationResponse[JSONValue])

    def handle[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        operation: str,
        status_code: int,
        content: str,
    ) -> ResultT:
        try:
            decoded = self._json_loads(content)
        except Exception as decoder_error:
            raise ClientDecodeError(
                method=method,
                operation=operation,
                status_code=status_code,
            ) from decoder_error

        try:
            envelope = self._envelope_adapter.validate_python(decoded)
        except ValidationError:
            raise ClientDecodeError(
                method=method,
                operation=operation,
                status_code=status_code,
            ) from None

        if not envelope.ok:
            raise PokerlostAPIError(
                method=method,
                operation=operation,
                status_code=status_code,
                error=cast(str, envelope.error),
                error_message=cast(str, envelope.error_message),
            )

        if not 200 <= status_code < 300:
            raise PokerlostProtocolError(
                method=method,
                operation=operation,
                status_code=status_code,
            )

        try:
            result = TypeAdapter(method.__returning__).validate_python(
                envelope.result,
                context={"client": method.client},
            )
        except ValidationError:
            raise ClientDecodeError(
                method=method,
                operation=operation,
                status_code=status_code,
            ) from None
        return cast(ResultT, result)
