from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from pypokerlost.transport.transport_request import TransportRequest
from pypokerlost.transport.transport_response import TransportResponse
from pypokerlost.types import JsonValue


def test_transport_request_copies_mappings_and_is_immutable() -> None:
    query = {"page": "1"}
    headers = {"x-request-id": "initial"}
    json_body: dict[str, JsonValue] = {"value": "payload"}
    request = TransportRequest(
        method="POST",
        path="/tests.echo",
        query=query,
        json=json_body,
        headers=headers,
    )

    query["page"] = "2"
    headers["x-request-id"] = "changed"
    json_body["value"] = "changed"

    assert request.query == {"page": "1"}
    assert request.headers == {"x-request-id": "initial"}
    mutable_headers = cast(MutableMapping[str, str], request.headers)
    with pytest.raises(TypeError):
        mutable_headers["new"] = "value"
    exposed_json = cast(dict[str, JsonValue], request.json)
    exposed_json["value"] = "changed through request"
    assert request.json == {"value": "payload"}
    with pytest.raises(FrozenInstanceError):
        request.path = "/changed"  # type: ignore[misc]


def test_transport_response_copies_headers_and_is_immutable() -> None:
    headers = {"content-type": "application/json"}
    response = TransportResponse(status_code=200, headers=headers, body=b"{}")
    headers["content-type"] = "text/plain"

    assert response.headers == {"content-type": "application/json"}
    mutable_headers = cast(MutableMapping[str, str], response.headers)
    with pytest.raises(TypeError):
        mutable_headers["new"] = "value"
    with pytest.raises(FrozenInstanceError):
        response.status_code = 500  # type: ignore[misc]
