from __future__ import annotations

from dataclasses import dataclass

from pypokerlost.types import HTTPMethod, RPCOperation


@dataclass(frozen=True, slots=True)
class RPCRequest:
    """Immutable transport-ready request for one RPC operation."""

    operation: RPCOperation
    http_method: HTTPMethod
    url: str
    content: bytes
    headers: tuple[tuple[str, str], ...] = ()
