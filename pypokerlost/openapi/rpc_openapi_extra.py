from pypokerlost.types import JsonValue

from .access_role import AccessRole
from .response_kind import ResponseKind

_CONTRACT_VERSION = 1
_EXTENSION_KEY = "x-pokerlost"


def rpc_openapi_extra(
    *,
    access: tuple[AccessRole, ...],
    success_response: ResponseKind = ResponseKind.APPLICATION_RESPONSE,
) -> dict[str, JsonValue]:
    """Build shared JSON-compatible metadata for a PokerLost RPC operation."""
    if not access:
        raise ValueError("access must contain at least one role")
    if len(access) != len(set(access)):
        raise ValueError("access must not contain duplicate roles")
    if AccessRole.PUBLIC in access and len(access) != 1:
        raise ValueError("AccessRole.PUBLIC cannot be combined with other roles")

    return {
        _EXTENSION_KEY: {
            "contract_version": _CONTRACT_VERSION,
            "access": {"any_of": [role.value for role in access]},
            "response": {
                "success": success_response.value,
                "error": ResponseKind.APPLICATION_RESPONSE.value,
            },
        },
    }
