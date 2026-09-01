"""Typed request construction for API operations."""

from __future__ import annotations

from pydantic import TypeAdapter

from pypokerlost.exceptions import ClientRequestError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import (
    APIOperation,
    HTTPMethod,
    HTTPRequestContentType,
    JSONValue,
)

from .request import Request
from .request_options import RequestOptions

_ACCEPT_HEADER = ("Accept", "application/json")


class RequestBuilder:
    """Build a validated transport-independent request from a typed method."""

    def __init__(self) -> None:
        self._operation_adapter: TypeAdapter[APIOperation] = TypeAdapter(APIOperation)
        self._http_method_adapter: TypeAdapter[HTTPMethod] = TypeAdapter(HTTPMethod)
        self._content_type_adapter: TypeAdapter[HTTPRequestContentType] = TypeAdapter(
            HTTPRequestContentType
        )

    def build[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        options: RequestOptions | None = None,
        operation: APIOperation | None = None,
        http_method: HTTPMethod | None = None,
        content_type: HTTPRequestContentType | None = None,
    ) -> Request:
        data: dict[str, JSONValue] | None = None
        request_options = RequestOptions()
        custom_header_names: set[str] = set()
        headers: tuple[tuple[str, str], ...] = ()
        request: Request | None = None
        failure: ClientRequestError | None = None
        data_outcome: dict[str, JSONValue] | ClientRequestError | None = None
        try:
            if operation is None and http_method is None and content_type is None:
                operation, http_method, content_type = self.describe(method)
            elif operation is None or http_method is None or content_type is None:
                raise TypeError(
                    "operation, http_method, and content_type must be supplied together"
                )
            data_outcome = self._dump_data(method, operation=operation)
            if isinstance(data_outcome, ClientRequestError):
                failure = data_outcome
            else:
                data = data_outcome

            request_options = options if options is not None else RequestOptions()
            custom_header_names = {name.casefold() for name, _ in request_options.headers}
            if "content-type" in custom_header_names:
                failure = ClientRequestError(method=method, operation=operation)
            default_headers = (("Content-Type", content_type), _ACCEPT_HEADER)
            headers = (
                tuple(
                    (name, value)
                    for name, value in default_headers
                    if name.casefold() not in custom_header_names
                )
                + request_options.headers
            )

            if failure is None and data is not None:
                try:
                    request = Request(
                        method=operation,
                        http_method=http_method,
                        content_type=content_type,
                        data=data,
                        headers=headers,
                    )
                except Exception:
                    failure = ClientRequestError(
                        method=method,
                        operation=operation,
                    )
            elif failure is None:
                failure = ClientRequestError(
                    method=method,
                    operation=operation,
                )
        finally:
            method = None  # type: ignore[assignment]
            options = None
            data = None
            data_outcome = None
            request_options = RequestOptions()
            custom_header_names = set()
            headers = ()

        if failure is not None:
            raise failure from None
        if request is None:
            raise AssertionError("Request construction completed without a result")
        return request

    def _dump_data[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        operation: APIOperation,
    ) -> dict[str, JSONValue] | ClientRequestError:
        try:
            try:
                return method.model_dump(
                    mode="json",
                    by_alias=False,
                    exclude_unset=True,
                )
            except Exception:
                return ClientRequestError(method=method, operation=operation)
        finally:
            method = None  # type: ignore[assignment]

    def describe[ResultT](
        self,
        method: PokerlostMethod[ResultT],
    ) -> tuple[APIOperation, HTTPMethod, HTTPRequestContentType]:
        """Validate and return immutable metadata used before transport execution."""
        try:
            return (
                self._parse_operation(method),
                self._parse_http_method(method),
                self._parse_content_type(method),
            )
        finally:
            method = None  # type: ignore[assignment]

    def _parse_operation[ResultT](
        self,
        method: PokerlostMethod[ResultT],
    ) -> APIOperation:
        invalid = False
        try:
            try:
                return self._operation_adapter.validate_python(method.__api_method__)
            except Exception:
                invalid = True
        finally:
            method = None  # type: ignore[assignment]
        if not invalid:
            raise AssertionError("API operation validation completed without a result")
        raise TypeError(
            "Concrete methods must declare __api_method__ as namespace.someOperation",
        ) from TypeError("API operation validation failed")

    def _parse_http_method[ResultT](
        self,
        method: PokerlostMethod[ResultT],
    ) -> HTTPMethod:
        invalid = False
        try:
            try:
                return self._http_method_adapter.validate_python(
                    method.__http_method__,
                )
            except Exception:
                invalid = True
        finally:
            method = None  # type: ignore[assignment]
        if not invalid:
            raise AssertionError("HTTP method validation completed without a result")
        raise TypeError(
            "Concrete methods must declare __http_method__ as GET, POST, PUT, PATCH, or DELETE",
        ) from TypeError("HTTP method validation failed")

    def _parse_content_type[ResultT](
        self,
        method: PokerlostMethod[ResultT],
    ) -> HTTPRequestContentType:
        invalid = False
        try:
            try:
                return self._content_type_adapter.validate_python(
                    method.__request_content_type__,
                    strict=True,
                )
            except Exception:
                invalid = True
        finally:
            method = None  # type: ignore[assignment]
        if not invalid:
            raise AssertionError("Request content type validation completed without a result")
        raise TypeError(
            "Concrete methods must declare a supported __request_content_type__",
        ) from TypeError("Request content type validation failed")
