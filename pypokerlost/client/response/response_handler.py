"""PokerLost response envelope decoding and validation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from pydantic import TypeAdapter, ValidationError

from pypokerlost.exceptions import (
    ClientDecodeError,
    PokerlostAPIError,
    PokerlostProtocolError,
)
from pypokerlost.types import JSONLoads, JSONValue

from .base_response_handler import BaseResponseHandler
from .response import Response

if TYPE_CHECKING:
    from pypokerlost.methods import PokerlostMethod


class ResponseHandler(BaseResponseHandler):
    """Interpret the fixed public PokerLost response protocol."""

    def __init__(self, json_loads: JSONLoads = json.loads) -> None:
        self._json_loads = json_loads
        self._envelope_adapter = TypeAdapter(Response[JSONValue])

    def handle[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        operation: str,
        status_code: int,
        content: str,
        retry_after: float | None = None,
    ) -> ResultT:
        """Interpret a response using the method's current declared result type."""
        try:
            return self._handle_response(
                method=method,
                operation=operation,
                status_code=status_code,
                content=content,
                retry_after=retry_after,
                returning=None,
            )
        finally:
            method = None  # type: ignore[assignment]
            content = ""

    def _handle_with_metadata[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        operation: str,
        status_code: int,
        content: str,
        retry_after: float | None,
        returning: object,
    ) -> ResultT:
        """Interpret a response using one result type captured before middleware."""
        try:
            return self._handle_response(
                method=method,
                operation=operation,
                status_code=status_code,
                content=content,
                retry_after=retry_after,
                returning=returning,
            )
        finally:
            method = None  # type: ignore[assignment]
            content = ""
            returning = None

    def _handle_response[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        operation: str,
        status_code: int,
        content: str,
        retry_after: float | None,
        returning: Any | None = None,
    ) -> ResultT:
        decoded: Any = None
        envelope: Response[JSONValue] | None = None
        encoded_result: str | None = None
        result: Any = None
        try:
            decoded, decoder_failure = self._decode(content)
            if decoder_failure is not None:
                raise ClientDecodeError(
                    method=method,
                    operation=operation,
                    status_code=status_code,
                    retry_after=retry_after,
                ) from decoder_failure

            envelope, envelope_failure = self._validate_envelope(decoded)
            if envelope_failure is not None:
                raise ClientDecodeError(
                    method=method,
                    operation=operation,
                    status_code=status_code,
                    retry_after=retry_after,
                ) from envelope_failure
            envelope = cast(Response[JSONValue], envelope)

            if not envelope.ok:
                raise PokerlostAPIError(
                    method=method,
                    operation=operation,
                    status_code=status_code,
                    error=cast(str, envelope.error),
                    error_message=cast(str, envelope.error_message),
                    retry_after=retry_after,
                )

            if not 200 <= status_code < 300:
                raise PokerlostProtocolError(
                    method=method,
                    operation=operation,
                    status_code=status_code,
                    retry_after=retry_after,
                )

            encoded_result, encoding_failure = self._encode_result(envelope.result)
            if encoding_failure is not None:
                raise ClientDecodeError(
                    method=method,
                    operation=operation,
                    status_code=status_code,
                    retry_after=retry_after,
                ) from encoding_failure
            encoded_result = cast(str, encoded_result)

            result, result_failure = self._validate_result(
                method,
                encoded_result,
                returning=returning,
            )
            if result_failure is not None:
                raise ClientDecodeError(
                    method=method,
                    operation=operation,
                    status_code=status_code,
                    retry_after=retry_after,
                ) from result_failure
            return cast(ResultT, result)
        finally:
            method = None  # type: ignore[assignment]
            content = ""
            returning = None
            decoded = None
            envelope = None
            encoded_result = None
            result = None

    def _decode(self, content: str) -> tuple[Any, ValueError | None]:
        try:
            return self._json_loads(content), None
        except Exception:
            return None, ValueError("Response decoder failed")

    def _validate_envelope(
        self,
        decoded: Any,
    ) -> tuple[Response[JSONValue] | None, ValueError | None]:
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
        except TypeError, ValueError:
            return None, ValueError("Response result encoding failed")
        return encoded_result, None

    def _validate_result(
        self,
        method: PokerlostMethod[Any],
        encoded_result: str,
        *,
        returning: Any | None = None,
    ) -> tuple[Any, ValueError | None]:
        result: Any = None
        try:
            result_type = method.__returning__ if returning is None else returning
            result = TypeAdapter(result_type).validate_json(
                encoded_result,
                strict=True,
                context={"client": method.client},
            )
            return result, None
        except Exception:
            return None, ValueError("Response result validation failed")
        finally:
            method = None  # type: ignore[assignment]
            encoded_result = ""
            returning = None
            result = None
