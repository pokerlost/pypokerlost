from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pypokerlost.session.prepared_request import PreparedRequest
from pypokerlost.types import JsonValue

if TYPE_CHECKING:
    from pypokerlost.methods import BaseMethod


class RequestBuilder:
    """Build the single JSON-over-HTTP representation used by RPC methods."""

    def build(self, method: BaseMethod) -> PreparedRequest:
        payload = cast(JsonValue, method.model_dump(mode="json", by_alias=False))
        return PreparedRequest(
            method=method.http_method,
            path=f"/{method.operation}",
            json_body=payload,
        )
