from __future__ import annotations

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class APIServer:
    """Address template for Pokerlost RPC operations."""

    base: str

    def api_url(self, method: str) -> str:
        return self.base.format(method=method)

    @classmethod
    def from_base(cls, base: str) -> Self:
        normalized_base = base.rstrip("/")
        return cls(base=f"{normalized_base}/{{method}}")


PRODUCTION = APIServer.from_base("http://localhost:8080/api")
