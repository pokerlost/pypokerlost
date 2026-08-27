from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, AnyHttpUrl, StringConstraints, TypeAdapter

_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


def _normalize_api_base(value: str) -> str:
    url = _HTTP_URL_ADAPTER.validate_python(value, strict=True)
    if url.query is not None or url.fragment is not None:
        raise ValueError("API base must not include a query or fragment")
    return str(url).rstrip("/")


type APIBase = Annotated[
    str,
    StringConstraints(strict=True, min_length=1),
    AfterValidator(_normalize_api_base),
]
