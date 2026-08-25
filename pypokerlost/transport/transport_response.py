from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """A buffered transport response independent of an HTTP implementation."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))
        object.__setattr__(self, "body", bytes(self.body))

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300
