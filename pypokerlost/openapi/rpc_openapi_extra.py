from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pypokerlost.types import (
    JSONValue,
    OAuth2Scopes,
    OpenAPIContractVersion,
    OpenAPISecurityScheme,
)


class RPCOpenAPIExtra(BaseModel):
    """Generic OAuth2/OpenAPI metadata for one RPC operation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )

    security_scheme: OpenAPISecurityScheme
    scopes: OAuth2Scopes = ()
    contract_version: OpenAPIContractVersion = 1

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "security": [{self.security_scheme: list(self.scopes)}],
            "x-pokerlost": {
                "contract_version": self.contract_version,
            },
        }
