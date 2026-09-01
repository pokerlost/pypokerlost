"""Build the canonical public Pokerlost request envelope."""

from __future__ import annotations

from typing import cast

from pydantic import ValidationError

from pypokerlost.errors import PokerlostConfigurationError
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import PokerlostOperation, PokerlostRequest, canonicalize_pokerlost_scopes

from .pokerlost_request_options import PokerlostRequestOptions


class PokerlostRequestBuilder:
    """Validate method metadata and wrap its fields in exactly one payload envelope."""

    def build[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        options: PokerlostRequestOptions,
        /,
    ) -> PokerlostRequest[object]:
        operation: PokerlostOperation | None = None
        request = cast("PokerlostRequest[object]", None)
        try:
            operation = PokerlostOperation(method.operation)
            scopes = canonicalize_pokerlost_scopes(method.required_scopes)
            if method.returning is None:
                raise ValueError("Method returning metadata must be a type annotation")
            if scopes != method.required_scopes:
                raise ValueError("Method scopes must use canonical ordering")
            request = PokerlostRequest[object](payload=method)
            return request.bind_call(
                cast("PokerlostMethod[object]", method),
                options,
            )
        except AttributeError, TypeError, ValueError, ValidationError:
            raise PokerlostConfigurationError(
                "Pokerlost method metadata or payload is invalid",
                operation=operation,
            ) from None
        finally:
            method = cast("PokerlostMethod[ResultT]", None)
            request = cast("PokerlostRequest[object]", None)
