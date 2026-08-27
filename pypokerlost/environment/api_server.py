from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from pydantic import TypeAdapter, ValidationError

from pypokerlost.types import APIBase, RPCOperation

_API_BASE_ADAPTER: TypeAdapter[APIBase] = TypeAdapter(APIBase)


@dataclass(frozen=True, slots=True)
class APIServer:
    """Address template for Pokerlost RPC operations."""

    base: str

    def api_url(self, method: RPCOperation) -> str:
        return self.base.format(method=method)

    @classmethod
    def from_base(cls, base: APIBase) -> Self:
        try:
            normalized_base = _API_BASE_ADAPTER.validate_python(base)
        except ValidationError as error:
            raise TypeError("API base must be a str") from error
        return cls(base=f"{normalized_base}/{{method}}")


PRODUCTION = APIServer.from_base("http://localhost:8080/api")
