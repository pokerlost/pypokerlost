from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

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
        decoded, decoder_failure = self._decode(content)
        if decoder_failure is not None:
            raise ClientDecodeError(
                method=method,
                operation=operation,
                status_code=status_code,
            ) from decoder_failure

        envelope, envelope_failure = self._validate_envelope(decoded)
        if envelope_failure is not None:
            raise ClientDecodeError(
                method=method,
                operation=operation,
                status_code=status_code,
            ) from envelope_failure
        envelope = cast(ApplicationResponse[JSONValue], envelope)

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

        encoded_result, encoding_failure = self._encode_result(envelope.result)
        if encoding_failure is not None:
            raise ClientDecodeError(
                method=method,
                operation=operation,
                status_code=status_code,
            ) from encoding_failure
        encoded_result = cast(str, encoded_result)

        result, result_failure = self._validate_result(method, encoded_result)
        if result_failure is not None:
            raise ClientDecodeError(
                method=method,
                operation=operation,
                status_code=status_code,
            ) from result_failure
        return cast(ResultT, result)

    def _decode(self, content: str) -> tuple[Any, ValueError | None]:
        try:
            return self._json_loads(content), None
        except Exception:
            return None, ValueError("Response decoder failed")

    def _validate_envelope(
        self,
        decoded: Any,
    ) -> tuple[ApplicationResponse[JSONValue] | None, ValueError | None]:
        try:
            envelope = self._envelope_adapter.validate_python(decoded, strict=True)
        except ValidationError:
            return None, ValueError("Response envelope validation failed")
        return envelope, None

    def _encode_result(
        self,
        result: JSONValue,
    ) -> tuple[str | None, ValueError | None]:
        try:
            encoded_result = json.dumps(
                result,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError):
            return None, ValueError("Response result encoding failed")
        return encoded_result, None

    def _validate_result[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        encoded_result: str,
    ) -> tuple[ResultT | None, ValueError | None]:
        try:
            result = TypeAdapter(method.__returning__).validate_json(
                encoded_result,
                strict=True,
                context={"client": method.client},
            )
        except ValidationError:
            return None, ValueError("Response result validation failed")
        return cast(ResultT, result), None
