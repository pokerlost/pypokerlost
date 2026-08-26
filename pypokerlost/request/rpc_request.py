from __future__ import annotations

from dataclasses import dataclass

from pypokerlost.enums import ServiceName


@dataclass(frozen=True, slots=True)
class RpcRequest:
    """Immutable transport-ready request for one RPC operation."""

    service: ServiceName
    operation: str
    http_method: str
    url: str
    content: bytes
