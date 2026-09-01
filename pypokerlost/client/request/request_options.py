"""Immutable per-request transport options."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from pypokerlost.client.retry import RetryPolicy

type _HTTPHeaderName = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        pattern=r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$",
    ),
]
type _HTTPHeaderValue = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[\t\x20-\x7e]*$",
    ),
]
type _HTTPHeaders = tuple[tuple[_HTTPHeaderName, _HTTPHeaderValue], ...]
_HTTP_HEADERS_ADAPTER: TypeAdapter[_HTTPHeaders] = TypeAdapter(
    _HTTPHeaders,
    config=ConfigDict(strict=True),
)


def _replace_invalid_http_headers(value: Any) -> _HTTPHeaders | None:
    try:
        return _HTTP_HEADERS_ADAPTER.validate_python(value)
    except ValidationError:
        return None


type _SafeHTTPHeaders = Annotated[
    _HTTPHeaders,
    BeforeValidator(_replace_invalid_http_headers),
]


class RequestOptions(BaseModel):
    """Immutable transport options propagated through one middleware chain."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    headers: _SafeHTTPHeaders = Field(default=(), repr=False, exclude=True)
    retry: RetryPolicy | None = None

    @model_validator(mode="before")
    def _replace_extra_input_values(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: item if key in {"headers", "retry"} else None for key, item in value.items()
            }
        return value

    def with_headers(self, headers: Mapping[str, str]) -> Self:
        """Return a copy with case-insensitive header replacements."""
        additions = type(self)(headers=tuple(headers.items())).headers
        replaced_names = {name.casefold() for name, _ in additions}
        retained_headers = tuple(
            (name, value) for name, value in self.headers if name.casefold() not in replaced_names
        )
        return type(self)(
            headers=retained_headers + additions,
            retry=self.retry,
        )
