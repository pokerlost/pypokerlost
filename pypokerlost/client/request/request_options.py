"""Immutable per-request transport options."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from pypokerlost.client.retry import PokerLostRetryPolicy

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


def _canonicalize_http_headers(
    headers: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    seen_names: set[str] = set()
    for name, _ in headers:
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            raise ValueError("HTTP header names must be unique case-insensitively")
        seen_names.add(normalized_name)
    return tuple(sorted(headers, key=lambda item: (item[0].casefold(), item[0])))


type _HTTPHeaders = Annotated[
    tuple[tuple[_HTTPHeaderName, _HTTPHeaderValue], ...],
    AfterValidator(_canonicalize_http_headers),
]
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
    """Immutable headers and optional retry policy for one transport call."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    headers: _SafeHTTPHeaders = Field(default=(), repr=False, exclude=True)
    retry: PokerLostRetryPolicy | None = None

    @model_validator(mode="before")
    def _replace_extra_input_values(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: item if key in {"headers", "retry"} else None for key, item in value.items()
            }
        return value

    def with_headers(self, headers: Mapping[str, str]) -> Self:
        """Return a copy with case-insensitive header replacements."""
        additions: _HTTPHeaders = ()
        invalid_headers = False
        replaced_names: set[str] = set()
        retained_headers: _HTTPHeaders = ()
        try:
            additions = _HTTP_HEADERS_ADAPTER.validate_python(tuple(headers.items()))
            replaced_names = {name.casefold() for name, _ in additions}
            retained_headers = tuple(
                (name, value)
                for name, value in self.headers
                if name.casefold() not in replaced_names
            )
            return type(self)(
                headers=retained_headers + additions,
                retry=self.retry,
            )
        except Exception:
            invalid_headers = True
        finally:
            headers = {}
            additions = ()
            replaced_names = set()
            retained_headers = ()
        if not invalid_headers:
            raise AssertionError("HTTP header update completed without a result")
        raise ValueError("HTTP headers are invalid") from None
