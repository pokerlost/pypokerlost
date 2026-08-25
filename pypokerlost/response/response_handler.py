from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic import TypeAdapter, ValidationError

from pypokerlost.contracts import ApplicationResponse
from pypokerlost.errors import ApplicationError, ResponseDecodeError, UnexpectedStatusError

if TYPE_CHECKING:
    from pypokerlost.methods import Method, StreamMethod
    from pypokerlost.session.content_stream import ContentStream
    from pypokerlost.session.raw_response import RawResponse

_ERROR_RESPONSE_LIMIT = 512


class ResponseHandler:
    """Apply the shared HTTP-status and ApplicationResponse policy."""

    def handle[ResultT](self, method: Method[ResultT], response: RawResponse) -> ResultT:
        try:
            envelope = self._decode_envelope(response.body, result_type=method.result_type)
        except ValidationError as error:
            if self._is_success(response.status_code):
                raise ResponseDecodeError(
                    operation=method.operation,
                    status_code=response.status_code,
                    detail="response body does not match ApplicationResponse contract",
                ) from error
            raise UnexpectedStatusError(
                response.status_code,
                operation=method.operation,
                response_body=response.body,
            ) from error

        if not envelope.ok:
            raise self._application_error(
                envelope,
                operation=method.operation,
                status_code=response.status_code,
            )
        if not self._is_success(response.status_code):
            raise UnexpectedStatusError(
                response.status_code,
                operation=method.operation,
                response_body=response.body,
            )
        return cast(ResultT, envelope.result)

    async def validate_stream_response(
        self,
        method: StreamMethod,
        content: ContentStream,
    ) -> None:
        if self._is_success(content.status_code):
            return

        response_body = await content.read_excerpt(_ERROR_RESPONSE_LIMIT + 1)
        try:
            envelope = self._decode_envelope(response_body, result_type=None)
        except ValidationError as error:
            raise UnexpectedStatusError(
                content.status_code,
                operation=method.operation,
                response_body=response_body,
            ) from error

        if not envelope.ok:
            raise self._application_error(
                envelope,
                operation=method.operation,
                status_code=content.status_code,
            )
        raise UnexpectedStatusError(
            content.status_code,
            operation=method.operation,
            response_body=response_body,
        )

    @staticmethod
    def _decode_envelope(body: bytes, *, result_type: Any) -> ApplicationResponse[Any]:
        adapter = TypeAdapter(ApplicationResponse[result_type])
        return adapter.validate_json(body)

    @staticmethod
    def _application_error(
        envelope: ApplicationResponse[Any],
        *,
        operation: str,
        status_code: int,
    ) -> ApplicationError:
        return ApplicationError(
            error=cast(str, envelope.error),
            error_message=cast(str, envelope.error_message),
            operation=operation,
            status_code=status_code,
        )

    @staticmethod
    def _is_success(status_code: int) -> bool:
        return 200 <= status_code < 300
