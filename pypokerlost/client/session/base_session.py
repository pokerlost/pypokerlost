"""Abstract asynchronous transport session."""

from __future__ import annotations

import abc
from inspect import getattr_static
from types import TracebackType
from typing import Any, Self, cast

from pypokerlost.client.request import RequestBuilder, RequestOptions
from pypokerlost.client.response import BaseResponseHandler
from pypokerlost.exceptions import ClientRequestError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import APIOperation, HTTPMethod

DEFAULT_TIMEOUT = 10


class BaseSession(abc.ABC):
    """Orchestrate request building, execution, and response handling."""

    def __init__(
        self,
        *,
        request_builder: RequestBuilder,
        response_handler: BaseResponseHandler,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._request_builder = request_builder
        self._response_handler = response_handler
        self._timeout = timeout

    @property
    def request_builder(self) -> RequestBuilder:
        return self._request_builder

    @property
    def response_handler(self) -> BaseResponseHandler:
        return self._response_handler

    @property
    def timeout(self) -> int:
        return self._timeout

    async def start(self) -> None:  # noqa: B027
        """Start session resources; the default implementation has none."""

    async def __call__[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        timeout: int | None = None,
        *,
        options: RequestOptions | None = None,
    ) -> ResultT:
        effective_timeout = self.timeout if timeout is None else timeout
        request_options = options if options is not None else RequestOptions()
        try:
            return await self.make_request(
                method,
                timeout=effective_timeout,
                options=request_options,
            )
        finally:
            method = None  # type: ignore[assignment]
            options = None
            request_options = RequestOptions()

    async def _make_request_with_metadata[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        *,
        operation: APIOperation,
        http_method: HTTPMethod,
        returning: object,
        timeout: int | None = None,
        options: RequestOptions | None = None,
    ) -> ResultT:
        """Execute captured metadata; custom sessions retain their existing fallback."""
        method_type: type[Any] | None = None
        metadata: dict[str, object] = {}
        captured_method = cast("PokerlostMethod[ResultT]", None)
        setup_failure: ClientRequestError | None = None
        try:
            try:
                method_type = type(method)
                metadata = {
                    "__api_method__": operation,
                    "__http_method__": http_method,
                    "__returning__": returning,
                }
                if any(
                    hasattr(getattr_static(method_type, name, None), "__set__") for name in metadata
                ):
                    captured_method_type: Any = type(
                        f"_Captured{method_type.__name__}",
                        (method_type,),
                        {"__module__": method_type.__module__, **metadata},
                    )
                    captured_method = cast(
                        "PokerlostMethod[ResultT]",
                        captured_method_type.model_validate(
                            method.model_dump(
                                mode="python",
                                by_alias=False,
                                exclude_unset=True,
                            ),
                        ),
                    )
                else:
                    captured_method = method.model_copy(deep=True)
                    captured_method.__dict__.update(metadata)
            except Exception:
                setup_failure = ClientRequestError(
                    method=method,
                    operation=operation,
                )

            if setup_failure is None:
                return await self(captured_method, timeout=timeout, options=options)
        finally:
            method = None  # type: ignore[assignment]
            captured_method = cast("PokerlostMethod[ResultT]", None)
            method_type = None
            metadata = {}
            options = None

        if setup_failure is None:
            raise AssertionError("Session request setup completed without a result")
        raise setup_failure from None

    @abc.abstractmethod
    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        timeout: int,
        *,
        options: RequestOptions,
    ) -> ResultT:
        """Send one method and return its declared result."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Close resources held by the session."""

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
