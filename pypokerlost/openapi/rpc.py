from collections.abc import Iterable
from enum import StrEnum

from pypokerlost.types import JsonValue


class AccessRole(StrEnum):
    """Actor roles understood by the PokerLost OpenAPI contract."""

    PUBLIC = "public"
    USER = "user"
    SUPPORT = "support"
    MASTER = "master"
    AUTO = "auto"


def rpc_openapi_extra(
    *,
    access: Iterable[AccessRole],
) -> dict[str, JsonValue]:
    """Build fresh JSON-compatible metadata for a PokerLost RPC operation."""
    return {
        "x-pokerlost": {
            "access": [role.value for role in access],
        },
    }
