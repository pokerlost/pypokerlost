from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from pypokerlost.types import (
    JSONValue,
    OAuth2Scopes,
    OpenAPIContractVersion,
    OpenAPISecurityScheme,
)


class _RPCOpenAPIExtraInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )

    security_scheme: OpenAPISecurityScheme
    scopes: OAuth2Scopes = ()
    contract_version: OpenAPIContractVersion = 1


_RPC_OPENAPI_EXTRA_ADAPTER = TypeAdapter(_RPCOpenAPIExtraInput)


@dataclass(frozen=True, slots=True)
class RPCOpenAPIExtra:
    """Generic OAuth2/OpenAPI metadata for one RPC operation."""

    security_scheme: OpenAPISecurityScheme
    scopes: OAuth2Scopes = ()
    contract_version: OpenAPIContractVersion = 1

    def __post_init__(self) -> None:
        try:
            _RPC_OPENAPI_EXTRA_ADAPTER.validate_python(
                {
                    "security_scheme": self.security_scheme,
                    "scopes": self.scopes,
                    "contract_version": self.contract_version,
                },
            )
        except ValidationError as error:
            raise ValueError("RPC OpenAPI metadata is invalid") from error

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "security": [{self.security_scheme: list(self.scopes)}],
            "x-pokerlost": {
                "contract_version": self.contract_version,
            },
        }
