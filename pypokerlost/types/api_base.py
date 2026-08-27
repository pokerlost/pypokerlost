from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def _normalize_api_base(value: str) -> str:
    return value.rstrip("/")


type APIBase = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(_normalize_api_base),
]
