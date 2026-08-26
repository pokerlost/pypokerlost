from dataclasses import dataclass

from pypokerlost.enums import AccessRole, ServiceName
from pypokerlost.types import JsonValue


@dataclass(frozen=True, slots=True)
class RpcOpenApiExtra:
    """JSON-compatible service and access metadata for one RPC operation."""

    service: ServiceName
    access: tuple[AccessRole, ...]
    contract_version: int = 1

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "x-pokerlost": {
                "contract_version": self.contract_version,
                "service": self.service.value,
                "access": [role.value for role in self.access],
            },
        }
