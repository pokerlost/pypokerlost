"""Small synthetic OpenAPI inputs for the actual SDK generator."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pypokerlost.enums import PokerlostScopes
from pypokerlost.types import PokerlostResponse

SCOPE = PokerlostScopes.ACCOUNTS_SELF_GET_ME.value


def object_schema(
    properties: dict[str, Any] | None = None, required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


def document(
    operation: str = "technicalProbe",
    *,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    protected: bool = False,
) -> dict[str, Any]:
    response = PokerlostResponse[int].model_json_schema()
    response["properties"]["result"] = {"anyOf": [result or {"type": "integer"}, {"type": "null"}]}
    contract: dict[str, Any] = {
        "operationId": operation,
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": object_schema({"payload": payload or object_schema()}, ["payload"])
                }
            },
        },
        "responses": {
            "200": {
                "description": "Technical success",
                "content": {"application/json": {"schema": response}},
            }
        },
    }
    root: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": "Technical fixture", "version": "1.0.0"},
        "paths": {f"/{operation}": {"post": contract}},
        "components": {"schemas": {}},
    }
    if protected:
        contract["security"] = [{"PokerlostOAuth2": [SCOPE]}]
        root["components"]["securitySchemes"] = {
            "PokerlostOAuth2": {
                "type": "oauth2",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": "/getToken",
                        "scopes": {SCOPE: "Read the synthetic identity"},
                    }
                },
            }
        }
    return deepcopy(root)


def operation(raw: dict[str, Any]) -> dict[str, Any]:
    return next(iter(raw["paths"].values()))["post"]


def success_schema(raw: dict[str, Any]) -> dict[str, Any]:
    return operation(raw)["responses"]["200"]["content"]["application/json"]["schema"]


def handwritten(
    *, result: str = "int", returning: str = "int", field: str = "", scopes: str = "None"
) -> str:
    return (
        "from pypokerlost.methods import PokerlostMethod\n"
        "from pypokerlost.types import PokerlostOperation\n"
        "from pypokerlost.enums import PokerlostScopes\nfrom typing import ClassVar\n\n"
        f"class TechnicalProbe(PokerlostMethod[{result}]):\n"
        '    operation = PokerlostOperation("technicalProbe")\n'
        f"    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = {scopes}\n"
        f"    returning = {returning}\n" + ("    " + field + "\n" if field else "")
    )
