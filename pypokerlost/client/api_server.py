"""Validated API server targeting for PokerLost operations."""

from __future__ import annotations

from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from pypokerlost.types import APIBase, APIOperation

_API_BASE_ADAPTER: TypeAdapter[APIBase] = TypeAdapter(APIBase)
_API_TEMPLATE_SUFFIX = "/{method}"


def _normalize_api_template(value: str) -> str:
    if not value.endswith(_API_TEMPLATE_SUFFIX) or value.count("{method}") != 1:
        raise ValueError("API server template must end with exactly one /{method}")
    normalized_base = _API_BASE_ADAPTER.validate_python(
        value.removesuffix(_API_TEMPLATE_SUFFIX),
    )
    return f"{normalized_base}{_API_TEMPLATE_SUFFIX}"


type _ValidatedAPITemplate = Annotated[
    str,
    StringConstraints(strict=True, min_length=1),
    AfterValidator(_normalize_api_template),
]
_API_TEMPLATE_ADAPTER: TypeAdapter[_ValidatedAPITemplate] = TypeAdapter(
    _ValidatedAPITemplate,
    config=ConfigDict(strict=True),
)


def _replace_invalid_api_template(value: Any) -> str | None:
    try:
        return _API_TEMPLATE_ADAPTER.validate_python(value)
    except ValidationError as error:
        if any(detail["type"] == "string_type" for detail in error.errors()):
            return None
        return ""


type _APITemplate = Annotated[
    _ValidatedAPITemplate,
    BeforeValidator(_replace_invalid_api_template),
]


class APIServer(BaseModel):
    """Address template for PokerLost API operations."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        hide_input_in_errors=True,
    )

    base: _APITemplate

    @model_validator(mode="before")
    def _replace_extra_input_values(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: item if key == "base" else None for key, item in value.items()}
        return value

    def api_url(self, method: APIOperation) -> str:
        return self.base.format(method=method)

    @classmethod
    def from_base(cls, base: APIBase) -> Self:
        try:
            normalized_base = _API_BASE_ADAPTER.validate_python(base)
        except ValidationError as error:
            invalid_type = any(detail["type"] == "string_type" for detail in error.errors())
        else:
            return cls(base=f"{normalized_base}/{{method}}")
        if invalid_type:
            raise TypeError("API base must be a str") from TypeError(
                "API base validation failed",
            )
        raise ValueError(
            "API base must be a valid HTTP(S) URL without user information, query, or fragment",
        ) from ValueError("API base validation failed")


PRODUCTION = APIServer.from_base("http://localhost:8080/api")
