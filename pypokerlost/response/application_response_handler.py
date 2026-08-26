from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from pydantic import TypeAdapter, ValidationError

from pypokerlost.contracts import ApplicationResponse
from pypokerlost.enums import ServiceName
from pypokerlost.exceptions import (
    ClientDecodeError,
    PokerlostAPIError,
    PokerlostBadRequestError,
    PokerlostConflictError,
    PokerlostEntityTooLargeError,
    PokerlostForbiddenError,
    PokerlostNotFoundError,
    PokerlostProtocolError,
    PokerlostServerError,
    PokerlostTooManyRequestsError,
    PokerlostUnauthorizedError,
    PokerlostValidationError,
)
from pypokerlost.response.base_response_handler import BaseResponseHandler
from pypokerlost.types import JSONLoads, JsonValue

if TYPE_CHECKING:
    from pypokerlost.methods import PokerlostMethod


class ApplicationResponseHandler(BaseResponseHandler):
    """Interpret the fixed public ``ApplicationResponse`` protocol."""

    def __init__(self, json_loads: JSONLoads = json.loads) -> None:
        self._json_loads = json_loads
        self._envelope_adapter = TypeAdapter(ApplicationResponse[JsonValue])

    def handle[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        service: ServiceName,
        operation: str,
        status_code: int,
        content: str,
    ) -> ResultT:
        try:
            decoded = self._json_loads(content)
        except Exception as decoder_error:
            raise ClientDecodeError(
                method=method,
                service=service,
                operation=operation,
                status_code=status_code,
            ) from decoder_error

        try:
            envelope = self._envelope_adapter.validate_python(decoded)
        except ValidationError:
            raise ClientDecodeError(
                method=method,
                service=service,
                operation=operation,
                status_code=status_code,
            ) from None

        if not envelope.ok:
            error = envelope.error
            error_message = envelope.error_message
            if error is None or error_message is None:
                raise ClientDecodeError(
                    method=method,
                    service=service,
                    operation=operation,
                    status_code=status_code,
                )
            raise self._api_error_type(status_code)(
                method=method,
                service=service,
                operation=operation,
                status_code=status_code,
                error=error,
                error_message=error_message,
            )

        if not 200 <= status_code < 300:
            raise PokerlostProtocolError(
                method=method,
                service=service,
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
                service=service,
                operation=operation,
                status_code=status_code,
            ) from None
        return cast(ResultT, result)

    def _api_error_type(self, status_code: int) -> type[PokerlostAPIError]:
        if status_code == 400:
            return PokerlostBadRequestError
        if status_code == 401:
            return PokerlostUnauthorizedError
        if status_code == 403:
            return PokerlostForbiddenError
        if status_code == 404:
            return PokerlostNotFoundError
        if status_code == 409:
            return PokerlostConflictError
        if status_code == 413:
            return PokerlostEntityTooLargeError
        if status_code == 422:
            return PokerlostValidationError
        if status_code == 429:
            return PokerlostTooManyRequestsError
        if status_code >= 500:
            return PokerlostServerError
        return PokerlostAPIError
