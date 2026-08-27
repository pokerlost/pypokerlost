#!/usr/bin/env python3
"""Generate typed Pokerlost SDK methods from a Pokerlost service OpenAPI contract.

Typer commands:

    python scripts/generate_methods.py file path/to/openapi.json
    python scripts/generate_methods.py service http://localhost:8080
    python scripts/generate_methods.py --help

The service mode reads the service template's wrapped ``GET /openapi.get`` endpoint.

Generation policy:

- OpenAPI ``info.version`` must be SemVer.
- ``GENERATOR_VERSION`` follows SemVer:
  MAJOR = incompatible generated layout/public-contract changes;
  MINOR = backward-compatible generation capabilities;
  PATCH = generator bug fixes that do not intentionally change generated public contracts.
- A contract whose canonical content changes without an OpenAPI version precedence increase is
  rejected unless ``--force`` is supplied.
- Generated files are deterministic: no timestamps and stable ordering.
- Only files listed in the generator manifest are overwritten or removed.
- Unsupported OpenAPI constructs fail explicitly instead of being guessed.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import keyword
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Any, Literal, Never, Self
from uuid import uuid4

import aiofiles
import aiofiles.os
import httpx
import typer
from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from pypokerlost.contracts import ApplicationResponse
from pypokerlost.types import HTTPMethod, JSONValue, RPCOperation

GENERATOR_VERSION_TEXT = "0.2.1"
OPENAPI_ENDPOINT = "/openapi.get"
DEFAULT_OUTPUT = Path("pypokerlost/methods")
MANIFEST_DIRECTORY = Path(__file__).resolve().parent / ".generated_methods"
EXPLICIT_NULL_REJECTOR_SOURCE = (
    "def _reject_explicit_null[ValueT](value: ValueT | None) -> ValueT:\n"
    "    if value is None:\n"
    '        raise ValueError("Field does not accept null")\n'
    "    return value"
)

SYSTEM_PATHS = frozenset({"/", OPENAPI_ENDPOINT})

VERSION_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
RPC_OPERATION_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
SERVICE_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"
PYTHON_CLASS_PATTERN = r"^[A-Z][A-Za-z0-9]*$"
PYTHON_FIELD_PATTERN = r"^[a-z_][a-z0-9_]*$"
PYTHON_PACKAGE_PATTERN = r"^[a-z_][a-z0-9_]*$"
SUPPORTED_STRING_FORMATS = frozenset({"uuid", "date", "date-time", "time"})
SUPPORTED_JSON_SCHEMA_DIALECTS = frozenset(
    {
        "https://json-schema.org/draft/2020-12/schema",
        "https://spec.openapis.org/oas/3.1/dialect/base",
    }
)
PASCAL_CASE_ACRONYMS = {
    "api": "API",
    "http": "HTTP",
    "httpx": "Httpx",
    "json": "JSON",
    "oauth2": "OAuth2",
    "openapi": "OpenAPI",
    "rpc": "RPC",
    "sdk": "SDK",
    "ttl": "TTL",
    "url": "URL",
    "uuid": "UUID",
}
RESERVED_GENERATED_CLASS_NAMES = frozenset(
    {
        "Annotated",
        "BaseModel",
        "BeforeValidator",
        "ConfigDict",
        "Field",
        "JSONValue",
        "Literal",
        "PokerlostMethod",
        "UUID",
    }
)
RESERVED_GENERATED_FIELD_NAMES = frozenset(
    {
        "as_",
        "client",
        "construct",
        "copy",
        "dict",
        "emit",
        "from_orm",
        "json",
        "parse_file",
        "parse_obj",
        "parse_raw",
        "resolve_client",
        "schema",
        "schema_json",
        "update_forward_refs",
        "validate",
    }
)

APPLICATION_RESPONSE_FIELDS = frozenset(ApplicationResponse.model_fields)
APPLICATION_RESPONSE_REQUIRED_FIELDS = frozenset(
    name for name, field in ApplicationResponse.model_fields.items() if field.is_required()
)

JSON_SCHEMA_METADATA_FIELDS = frozenset({"$comment", "deprecated", "example", "examples"})
MEDIA_TYPE_METADATA_FIELDS = frozenset({"example", "examples"})
OPERATION_METADATA_FIELDS = frozenset(
    {"description", "externalDocs", "security", "summary", "tags"}
)
PATH_ITEM_METADATA_FIELDS = frozenset({"description", "summary"})
COMPONENT_METADATA_FIELDS = frozenset(
    {
        "callbacks",
        "examples",
        "headers",
        "links",
        "parameters",
        "pathItems",
        "securitySchemes",
    }
)
INFO_METADATA_FIELDS = frozenset({"contact", "description", "license", "summary", "termsOfService"})
DOCUMENT_METADATA_FIELDS = frozenset(
    {"externalDocs", "jsonSchemaDialect", "security", "servers", "tags", "webhooks"}
)


def reject_python_keyword(value: str) -> str:
    if keyword.iskeyword(value):
        raise ValueError("Python keyword is not a valid generated identifier")
    return value


def validate_generated_field_name(value: str) -> str:
    if value.startswith("_"):
        raise ValueError("Generated field names cannot start with an underscore")
    if value.startswith("model_") or value in RESERVED_GENERATED_FIELD_NAMES:
        raise ValueError("Generated field name conflicts with the public method model API")
    return value


def validate_generated_rpc_operation(
    value: RPCOperation,
) -> RPCOperation:
    if re.fullmatch(RPC_OPERATION_PATTERN, value) is None:
        raise ValueError("Generated RPC operation must use lowercase namespace.method syntax")
    return value


def validate_generated_path(value: str) -> str:
    path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or path.as_posix() != value
        or "\\" in value
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise ValueError("Generated path must be normalized and relative")
    if path.suffix != ".py":
        raise ValueError("Generated path must identify a Python source file")
    return value


def reject_unsupported_openapi_fields(
    model: BaseModel,
    *,
    allowed: frozenset[str],
    node_name: str,
) -> None:
    extras = model.model_extra or {}
    unsupported = sorted(
        name for name in extras if name not in allowed and not name.startswith("x-")
    )
    if unsupported:
        fields = ", ".join(unsupported)
        raise ValueError(f"{node_name} contains unsupported fields: {fields}")


def validate_local_component_reference(value: str, component_group: str) -> None:
    prefix = f"#/components/{component_group}/"
    name = value.removeprefix(prefix)
    if not value.startswith(prefix) or not name or "/" in name:
        raise ValueError(f"unsupported OpenAPI component reference: {value}")


def json_value_kind(value: JSONValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise ValueError("Value is not JSON-compatible")


def validate_json_schema_pattern(value: str) -> str:
    try:
        TypeAdapter(Annotated[str, StringConstraints(pattern=value)])
    except Exception as error:
        raise ValueError("Pattern is not supported by Pydantic's regex engine") from error
    return value


VersionString = Annotated[
    str,
    StringConstraints(strict=True, pattern=VERSION_PATTERN),
]
GeneratedRPCOperation = Annotated[
    RPCOperation,
    AfterValidator(validate_generated_rpc_operation),
]
ServiceID = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, pattern=SERVICE_ID_PATTERN),
]
PythonClassName = Annotated[
    str,
    StringConstraints(strict=True, pattern=PYTHON_CLASS_PATTERN),
    AfterValidator(reject_python_keyword),
]
PythonFieldName = Annotated[
    str,
    StringConstraints(strict=True, pattern=PYTHON_FIELD_PATTERN),
    AfterValidator(reject_python_keyword),
    AfterValidator(validate_generated_field_name),
]
PythonPackageName = Annotated[
    str,
    StringConstraints(strict=True, pattern=PYTHON_PACKAGE_PATTERN),
    AfterValidator(reject_python_keyword),
]

RPC_OPERATION_ADAPTER = TypeAdapter(GeneratedRPCOperation)
PYTHON_CLASS_ADAPTER = TypeAdapter(PythonClassName)
PYTHON_PACKAGE_ADAPTER = TypeAdapter(PythonPackageName)


GeneratedPath = Annotated[
    str,
    StringConstraints(strict=True, min_length=1),
    AfterValidator(validate_generated_path),
]
NonEmptyString = Annotated[str, StringConstraints(strict=True, min_length=1)]
NonNegativeInteger = Annotated[int, Field(strict=True, ge=0)]
JSONSchemaPattern = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(validate_json_schema_pattern),
]
type JSONSchemaNumber = (
    Annotated[int, Field(strict=True)] | Annotated[float, Field(strict=True, allow_inf_nan=False)]
)


class GenerationError(RuntimeError):
    """Raised when a contract cannot be generated safely."""


class SemanticVersion(RootModel[VersionString]):
    """Validated MAJOR.MINOR.PATCH service/generator version."""

    model_config = ConfigDict(frozen=True)

    @property
    def parts(self) -> tuple[int, int, int]:
        major, minor, patch = self.root.split(".")
        return int(major), int(minor), int(patch)

    def compare(self, other: SemanticVersion) -> int:
        if self.parts == other.parts:
            return 0
        return -1 if self.parts < other.parts else 1


GENERATOR_VERSION = SemanticVersion.model_validate(GENERATOR_VERSION_TEXT)


class JSONSchema(BaseModel):
    """OpenAPI 3.1 JSON Schema subset consumed by the generator."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        validate_default=True,
    )

    ref: str | None = Field(default=None, alias="$ref")
    title: str | None = None
    description: str | None = None
    type: str | list[str] | None = None
    format: str | None = None

    properties: dict[PythonFieldName, JSONSchema] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    items: JSONSchema | None = None
    additional_properties: bool | JSONSchema | None = Field(
        default=None,
        alias="additionalProperties",
    )

    any_of: list[JSONSchema] = Field(default_factory=list, alias="anyOf")
    one_of: list[JSONSchema] = Field(default_factory=list, alias="oneOf")
    all_of: list[JSONSchema] = Field(default_factory=list, alias="allOf")

    enum: list[JSONValue] | None = None
    const: JSONValue = None
    default: JSONValue = None

    minimum: JSONSchemaNumber | None = None
    maximum: JSONSchemaNumber | None = None
    exclusive_minimum: JSONSchemaNumber | None = Field(default=None, alias="exclusiveMinimum")
    exclusive_maximum: JSONSchemaNumber | None = Field(default=None, alias="exclusiveMaximum")

    min_length: NonNegativeInteger | None = Field(default=None, alias="minLength")
    max_length: NonNegativeInteger | None = Field(default=None, alias="maxLength")
    pattern: JSONSchemaPattern | None = None

    min_items: NonNegativeInteger | None = Field(default=None, alias="minItems")
    max_items: NonNegativeInteger | None = Field(default=None, alias="maxItems")

    @model_validator(mode="after")
    def validate_supported_schema(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=JSON_SCHEMA_METADATA_FIELDS,
            node_name="JSON Schema",
        )

        if self.format is not None and self.format not in SUPPORTED_STRING_FORMATS:
            raise ValueError(f"unsupported JSON Schema string format: {self.format}")

        compositions = sum(bool(items) for items in (self.any_of, self.one_of, self.all_of))
        if compositions > 1:
            raise ValueError("JSON Schema cannot combine anyOf, oneOf, and allOf")

        for name, items in (
            ("anyOf", self.any_of),
            ("oneOf", self.one_of),
            ("allOf", self.all_of),
        ):
            field_name = to_snake_case(name)
            if field_name in self.model_fields_set and not items:
                raise ValueError(f"empty JSON Schema {name} is unsupported")

        if self.enum is not None and "const" in self.model_fields_set:
            raise ValueError("JSON Schema cannot combine enum and const")
        if self.enum is not None and not self.enum:
            raise ValueError("empty JSON Schema enum is unsupported")
        if self.enum is not None and any(
            json_value_kind(item) not in {"boolean", "integer", "null", "string"}
            for item in self.enum
        ):
            raise ValueError("JSON Schema enum supports Literal-compatible scalar values only")
        if "const" in self.model_fields_set and json_value_kind(self.const) not in {
            "boolean",
            "integer",
            "null",
            "string",
        }:
            raise ValueError("JSON Schema const supports a Literal-compatible scalar value only")
        if self.enum is not None or "const" in self.model_fields_set:
            ignored_literal_siblings = {
                "additional_properties",
                "all_of",
                "any_of",
                "items",
                "one_of",
                "properties",
                "required",
            }
            present_siblings = sorted(self.model_fields_set & ignored_literal_siblings)
            if present_siblings:
                names = ", ".join(present_siblings)
                raise ValueError(
                    f"JSON Schema enum or const has unsupported semantic siblings: {names}"
                )

        if self.ref is not None:
            validate_local_component_reference(self.ref, "schemas")
            annotations = {"ref", "title", "description"}
            model_extras = set(self.model_extra or {})
            siblings = self.model_fields_set - annotations - model_extras
            if siblings:
                names = ", ".join(sorted(siblings))
                raise ValueError(f"JSON Schema $ref has unsupported semantic siblings: {names}")

        union_field = "any_of" if self.any_of else "one_of" if self.one_of else None
        if union_field is not None:
            ignored_siblings = {
                "additional_properties",
                "all_of",
                "const",
                "enum",
                "exclusive_maximum",
                "exclusive_minimum",
                "format",
                "items",
                "max_items",
                "max_length",
                "maximum",
                "min_items",
                "min_length",
                "minimum",
                "pattern",
                "properties",
                "ref",
                "required",
                "type",
            }
            ignored_siblings.discard(union_field)
            present_siblings = sorted(self.model_fields_set & ignored_siblings)
            if present_siblings:
                names = ", ".join(present_siblings)
                raise ValueError(f"JSON Schema union has unsupported semantic siblings: {names}")

        if self.all_of:
            ignored_siblings = {"any_of", "const", "enum", "format", "items", "one_of"}
            present_siblings = sorted(self.model_fields_set & ignored_siblings)
            if present_siblings:
                names = ", ".join(present_siblings)
                raise ValueError(f"JSON Schema allOf has unsupported semantic siblings: {names}")
            schema_types = {self.type} if isinstance(self.type, str) else set(self.type or ())
            if schema_types and schema_types != {"object"}:
                raise ValueError(
                    "JSON Schema allOf is supported only for non-null object composition"
                )

        if len(set(self.required)) != len(self.required):
            raise ValueError("JSON Schema required fields must be unique")
        if not self.all_of:
            unknown_required = sorted(set(self.required) - set(self.properties))
            if unknown_required:
                names = ", ".join(unknown_required)
                raise ValueError(f"JSON Schema requires unknown properties: {names}")

        if self.properties and self.additional_properties is not False:
            raise ValueError("typed object schemas must set additionalProperties to false")
        schema_types = (
            set(self.type)
            if isinstance(self.type, list)
            else {self.type}
            if self.type is not None
            else set()
        )
        if self.properties and schema_types and schema_types != {"object"}:
            raise ValueError("typed object schemas must use the non-null object type")

        literal_kinds: set[str] = set()
        if self.enum is not None:
            literal_kinds.update(json_value_kind(item) for item in self.enum)
        if "const" in self.model_fields_set:
            literal_kinds.add(json_value_kind(self.const))

        if schema_types and any(
            kind not in schema_types and not (kind == "integer" and "number" in schema_types)
            for kind in literal_kinds
        ):
            raise ValueError("JSON Schema enum or const values do not match the declared type")
        if literal_kinds and self.format is not None:
            raise ValueError("JSON Schema enum or const cannot be combined with format")

        declared_kinds = schema_types | literal_kinds

        if self.format is not None and (
            not declared_kinds or not declared_kinds.issubset({"null", "string"})
        ):
            raise ValueError("JSON Schema string format requires a string schema")
        if any(
            value is not None for value in (self.min_length, self.max_length, self.pattern)
        ) and (not declared_kinds or not declared_kinds.issubset({"null", "string"})):
            raise ValueError("JSON Schema string constraints require a string schema")
        if any(value is not None for value in (self.min_items, self.max_items)) and (
            not declared_kinds or not declared_kinds.issubset({"array", "null"})
        ):
            raise ValueError("JSON Schema array constraints require an array schema")
        if any(
            value is not None
            for value in (
                self.minimum,
                self.maximum,
                self.exclusive_minimum,
                self.exclusive_maximum,
            )
        ) and (not declared_kinds or not declared_kinds.issubset({"integer", "null", "number"})):
            raise ValueError("JSON Schema numeric constraints require a numeric schema")

        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("JSON Schema minLength must not exceed maxLength")
        if (
            self.min_items is not None
            and self.max_items is not None
            and self.min_items > self.max_items
        ):
            raise ValueError("JSON Schema minItems must not exceed maxItems")

        return self


class OpenAPIMediaType(BaseModel):
    """OpenAPI media type containing one schema."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_: JSONSchema | None = Field(default=None, alias="schema")

    @model_validator(mode="after")
    def validate_supported_media_type(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=MEDIA_TYPE_METADATA_FIELDS,
            node_name="OpenAPI media type",
        )
        return self


class OpenAPIRequestBody(BaseModel):
    """Reference-capable OpenAPI request body."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    ref: str | None = Field(default=None, alias="$ref")
    description: str | None = None
    required: bool = False
    content: dict[str, OpenAPIMediaType] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_supported_request_body(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=frozenset(),
            node_name="OpenAPI request body",
        )
        if self.ref is not None:
            validate_local_component_reference(self.ref, "requestBodies")
        if self.ref is not None and self.model_fields_set - {"ref", "description"}:
            raise ValueError("OpenAPI request body $ref has unsupported semantic siblings")
        return self


class OpenAPIResponse(BaseModel):
    """Reference-capable OpenAPI response."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    ref: str | None = Field(default=None, alias="$ref")
    description: str = ""
    content: dict[str, OpenAPIMediaType] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_supported_response(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=frozenset(),
            node_name="OpenAPI response",
        )
        if self.ref is not None:
            validate_local_component_reference(self.ref, "responses")
        if self.ref is not None and self.model_fields_set - {"ref", "description"}:
            raise ValueError("OpenAPI response $ref has unsupported semantic siblings")
        return self


class OpenAPIParameter(BaseModel):
    """Operation parameter used only to reject unsupported transport shapes."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: NonEmptyString
    location: str = Field(alias="in")


class OpenAPIOperation(BaseModel):
    """OpenAPI operation subset needed for SDK generation."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    operation_id: NonEmptyString | None = Field(default=None, alias="operationId")
    deprecated: bool = False
    request_body: OpenAPIRequestBody | None = Field(default=None, alias="requestBody")
    parameters: list[OpenAPIParameter] = Field(default_factory=list)
    responses: dict[str, OpenAPIResponse]

    @model_validator(mode="after")
    def validate_supported_operation(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=OPERATION_METADATA_FIELDS,
            node_name="OpenAPI operation",
        )
        return self


class OpenAPIPathItem(BaseModel):
    """OpenAPI path item with supported HTTP operations."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    parameters: list[OpenAPIParameter] = Field(default_factory=list)

    get: OpenAPIOperation | None = None
    post: OpenAPIOperation | None = None
    put: OpenAPIOperation | None = None
    patch: OpenAPIOperation | None = None
    delete: OpenAPIOperation | None = None

    @model_validator(mode="after")
    def validate_supported_path_item(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=PATH_ITEM_METADATA_FIELDS,
            node_name="OpenAPI path item",
        )
        return self


class OpenAPIComponents(BaseModel):
    """OpenAPI components used by service contracts."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schemas: dict[str, JSONSchema] = Field(default_factory=dict)
    request_bodies: dict[str, OpenAPIRequestBody] = Field(
        default_factory=dict,
        alias="requestBodies",
    )
    responses: dict[str, OpenAPIResponse] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_supported_components(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=COMPONENT_METADATA_FIELDS,
            node_name="OpenAPI components",
        )
        return self


class OpenAPIInfo(BaseModel):
    """Required OpenAPI metadata."""

    model_config = ConfigDict(extra="allow")

    title: NonEmptyString
    version: SemanticVersion

    @model_validator(mode="after")
    def validate_supported_info(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=INFO_METADATA_FIELDS,
            node_name="OpenAPI info",
        )
        return self


class PokerlostServiceMetadata(BaseModel):
    """Pokerlost service identifier published by the service template."""

    model_config = ConfigDict(extra="forbid")

    id: ServiceID


class OpenAPIDocument(BaseModel):
    """Validated OpenAPI 3.1 Pokerlost service contract."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    openapi: SemanticVersion
    info: OpenAPIInfo
    paths: dict[str, OpenAPIPathItem]
    components: OpenAPIComponents = Field(default_factory=OpenAPIComponents)
    pokerlost_service: PokerlostServiceMetadata = Field(alias="x-pokerlost-service")

    @model_validator(mode="after")
    def validate_openapi_version(self) -> Self:
        reject_unsupported_openapi_fields(
            self,
            allowed=DOCUMENT_METADATA_FIELDS,
            node_name="OpenAPI document",
        )
        major, minor, _ = self.openapi.parts
        if (major, minor) != (3, 1):
            raise ValueError("generator supports OpenAPI 3.1.x only")
        dialect = (self.model_extra or {}).get("jsonSchemaDialect")
        if dialect is not None and (
            not isinstance(dialect, str) or dialect not in SUPPORTED_JSON_SCHEMA_DIALECTS
        ):
            raise ValueError(f"unsupported OpenAPI JSON Schema dialect: {dialect}")
        return self


OPENAPI_PUBLICATION_ADAPTER = TypeAdapter(ApplicationResponse[OpenAPIDocument])


class GenerationManifest(BaseModel):
    """Persistent generation state used for safe regeneration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    generator_version: SemanticVersion
    openapi_version: SemanticVersion
    source_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    service_id: ServiceID
    output_package: PythonPackageName
    files: tuple[GeneratedPath, ...]

    @model_validator(mode="after")
    def validate_owned_files(self) -> Self:
        if not self.files:
            raise ValueError("Generation manifest must own at least one file")
        if len(set(self.files)) != len(self.files):
            raise ValueError("Generation manifest file paths must be unique")
        if any(PurePosixPath(path).parts[0] != self.output_package for path in self.files):
            raise ValueError("Generation manifest files must stay inside the output package")
        return self


class FileGenerationSettings(BaseModel):
    """Validated local-file generation settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: Literal["file"]
    source: Path
    output: Path = DEFAULT_OUTPUT
    check: bool = False
    force: bool = False


class ServiceGenerationSettings(BaseModel):
    """Validated service-endpoint generation settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: Literal["service"]
    source: AnyHttpUrl
    output: Path = DEFAULT_OUTPUT
    check: bool = False
    force: bool = False
    timeout: Annotated[float, Field(strict=True, gt=0)] = 10.0


type GenerationSettings = Annotated[
    FileGenerationSettings | ServiceGenerationSettings,
    Field(discriminator="source_kind"),
]

GENERATION_SETTINGS_ADAPTER: TypeAdapter[GenerationSettings] = TypeAdapter(
    GenerationSettings,
)


@dataclass(frozen=True, slots=True, order=True)
class ImportSpec:
    """One generated Python import."""

    module: str
    name: str


@dataclass(frozen=True, slots=True)
class RenderedType:
    """Generated Python type expression plus required imports and model references."""

    expression: str
    imports: frozenset[ImportSpec] = frozenset()
    model_refs: frozenset[str] = frozenset()

    def nullable(self) -> RenderedType:
        if self.expression == "None" or self.expression.endswith(" | None"):
            return self
        return RenderedType(
            expression=f"{self.expression} | None",
            imports=self.imports,
            model_refs=self.model_refs,
        )


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """One validated RPC operation ready for code generation."""

    path: str
    http_method: HTTPMethod
    operation_id: GeneratedRPCOperation
    class_name: str
    file_name: str
    request_schema: JSONSchema | None
    result_schema: JSONSchema


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    """Generated repository file."""

    relative_path: Path
    content: str


class OpenAPIResolver:
    """Resolve local component references without guessing external contracts."""

    def __init__(self, document: OpenAPIDocument) -> None:
        self._document = document

    def resolve_schema(self, schema: JSONSchema) -> JSONSchema:
        if schema.ref is None:
            return schema
        name = self.schema_ref_name(schema.ref)
        try:
            return self._document.components.schemas[name]
        except KeyError as error:
            raise GenerationError(f"unknown schema reference: {schema.ref}") from error

    def resolve_request_body(self, body: OpenAPIRequestBody) -> OpenAPIRequestBody:
        if body.ref is None:
            return body
        name = self._component_ref_name(body.ref, "requestBodies")
        try:
            return self._document.components.request_bodies[name]
        except KeyError as error:
            raise GenerationError(f"unknown request body reference: {body.ref}") from error

    def resolve_response(self, response: OpenAPIResponse) -> OpenAPIResponse:
        if response.ref is None:
            return response
        name = self._component_ref_name(response.ref, "responses")
        try:
            return self._document.components.responses[name]
        except KeyError as error:
            raise GenerationError(f"unknown response reference: {response.ref}") from error

    def schema_ref_name(self, ref: str) -> str:
        return self._component_ref_name(ref, "schemas")

    def _component_ref_name(self, ref: str, group: str) -> str:
        prefix = f"#/components/{group}/"
        if not ref.startswith(prefix):
            raise GenerationError(
                f"external or unsupported OpenAPI reference is not allowed: {ref}"
            )
        name = ref.removeprefix(prefix)
        if not name or "/" in name:
            raise GenerationError(f"invalid component reference: {ref}")
        return name


class SchemaRenderer:
    """Translate the supported OpenAPI JSON Schema subset to Python/Pydantic source."""

    def __init__(self, resolver: OpenAPIResolver) -> None:
        self._resolver = resolver

    def render_type(self, schema: JSONSchema) -> RenderedType:
        if schema.ref is not None:
            name = self._resolver.schema_ref_name(schema.ref)
            validated_name = PYTHON_CLASS_ADAPTER.validate_python(name)
            return RenderedType(validated_name, model_refs=frozenset({validated_name}))

        if schema.any_of:
            return self._render_union(schema.any_of)
        if schema.one_of:
            return self._render_union(schema.one_of)
        if schema.all_of:
            normalized = self.merge_all_of(schema)
            return self.render_type(normalized)

        if schema.enum is not None:
            if not schema.enum:
                raise GenerationError("empty JSON Schema enum is unsupported")
            return RenderedType(
                expression=f"Literal[{', '.join(python_literal(item) for item in schema.enum)}]",
                imports=frozenset({ImportSpec("typing", "Literal")}),
            )

        if "const" in schema.model_fields_set:
            return RenderedType(
                expression=f"Literal[{python_literal(schema.const)}]",
                imports=frozenset({ImportSpec("typing", "Literal")}),
            )

        schema_types = self._schema_types(schema)
        nullable = "null" in schema_types
        concrete_types = [item for item in schema_types if item != "null"]

        if len(concrete_types) > 1:
            rendered = [self._render_primitive_type(item, schema) for item in concrete_types]
            result = self._combine_union(rendered)
        elif len(concrete_types) == 1:
            result = self._render_primitive_type(concrete_types[0], schema)
        elif nullable:
            return RenderedType("None")
        elif schema.properties or isinstance(schema.additional_properties, (bool, JSONSchema)):
            result = self._render_primitive_type("object", schema)
        else:
            raise GenerationError(
                f"schema has no supported type information: {schema.model_dump(by_alias=True)}"
            )

        return result.nullable() if nullable else result

    def merge_all_of(self, schema: JSONSchema) -> JSONSchema:
        if not schema.all_of:
            return schema

        properties: dict[str, JSONSchema] = {}
        required: list[str] = []
        additional_properties: bool | JSONSchema | None = None
        description = schema.description

        for item in schema.all_of:
            resolved = self._resolver.resolve_schema(item)
            if resolved.all_of:
                resolved = self.merge_all_of(resolved)

            schema_types = self._schema_types(resolved)
            if schema_types and any(value not in {"object", "null"} for value in schema_types):
                raise GenerationError("allOf is supported only for object schema composition")

            for name, property_schema in sorted(resolved.properties.items()):
                if name in properties:
                    raise GenerationError(f"allOf defines property {name!r} more than once")
                properties[name] = property_schema

            for name in resolved.required:
                if name not in required:
                    required.append(name)

            if resolved.additional_properties is not None:
                if (
                    additional_properties is not None
                    and resolved.additional_properties != additional_properties
                ):
                    raise GenerationError("allOf contains conflicting additionalProperties values")
                additional_properties = resolved.additional_properties

            if description is None:
                description = resolved.description

        for name, property_schema in sorted(schema.properties.items()):
            if name in properties:
                raise GenerationError(f"allOf defines property {name!r} more than once")
            properties[name] = property_schema

        for name in schema.required:
            if name not in required:
                required.append(name)

        return JSONSchema(
            type="object",
            description=description,
            properties=dict(sorted(properties.items())),
            required=sorted(required),
            additional_properties=(
                schema.additional_properties
                if schema.additional_properties is not None
                else additional_properties
            ),
        )

    def field_constraints(self, schema: JSONSchema) -> dict[str, JSONValue]:
        constraints: dict[str, JSONValue] = {}

        if schema.description:
            constraints["description"] = schema.description
        if schema.minimum is not None:
            constraints["ge"] = schema.minimum
        if schema.maximum is not None:
            constraints["le"] = schema.maximum
        if schema.exclusive_minimum is not None:
            constraints["gt"] = schema.exclusive_minimum
        if schema.exclusive_maximum is not None:
            constraints["lt"] = schema.exclusive_maximum
        if schema.min_length is not None:
            constraints["min_length"] = schema.min_length
        if schema.max_length is not None:
            constraints["max_length"] = schema.max_length
        if schema.pattern is not None:
            constraints["pattern"] = schema.pattern
        if schema.min_items is not None:
            constraints["min_length"] = schema.min_items
        if schema.max_items is not None:
            constraints["max_length"] = schema.max_items

        return constraints

    def collect_refs(self, schema: JSONSchema) -> set[str]:
        refs: set[str] = set()

        def visit(current: JSONSchema) -> None:
            if current.ref is not None:
                name = self._resolver.schema_ref_name(current.ref)
                if name in refs:
                    return
                refs.add(name)
                visit(self._resolver.resolve_schema(current))
                return

            for branch in (*current.any_of, *current.one_of, *current.all_of):
                visit(branch)

            for property_schema in current.properties.values():
                visit(property_schema)

            if current.items is not None:
                visit(current.items)

            if isinstance(current.additional_properties, JSONSchema):
                visit(current.additional_properties)

        visit(schema)
        return refs

    def value_kinds(self, schema: JSONSchema) -> set[str]:
        if schema.ref is not None:
            return self.value_kinds(self._resolver.resolve_schema(schema))
        if schema.any_of:
            return set().union(*(self.value_kinds(item) for item in schema.any_of))
        if schema.one_of:
            return set().union(*(self.value_kinds(item) for item in schema.one_of))
        if schema.all_of:
            merged = self.merge_all_of(schema)
            return self.value_kinds(merged)
        if schema.enum is not None:
            return {json_value_kind(item) for item in schema.enum}
        if "const" in schema.model_fields_set:
            return {json_value_kind(schema.const)}

        schema_types = set(self._schema_types(schema))
        if schema_types:
            return schema_types
        if schema.properties or isinstance(schema.additional_properties, (bool, JSONSchema)):
            return {"object"}
        if schema.items is not None:
            return {"array"}
        return set()

    def _render_union(self, schemas: Sequence[JSONSchema]) -> RenderedType:
        rendered = [self.render_type(item) for item in schemas]
        return self._combine_union(rendered)

    def _combine_union(self, rendered: Sequence[RenderedType]) -> RenderedType:
        expressions: list[str] = []
        imports: set[ImportSpec] = set()
        refs: set[str] = set()

        for item in rendered:
            imports.update(item.imports)
            refs.update(item.model_refs)
            if item.expression not in expressions:
                expressions.append(item.expression)

        if not expressions:
            raise GenerationError("empty union is unsupported")

        return RenderedType(
            expression=" | ".join(expressions),
            imports=frozenset(imports),
            model_refs=frozenset(refs),
        )

    def _render_primitive_type(self, schema_type: str, schema: JSONSchema) -> RenderedType:
        if schema_type == "string":
            if schema.format == "uuid":
                return RenderedType(
                    "UUID",
                    imports=frozenset({ImportSpec("uuid", "UUID")}),
                )
            if schema.format == "date-time":
                return RenderedType(
                    "datetime",
                    imports=frozenset({ImportSpec("datetime", "datetime")}),
                )
            if schema.format == "date":
                return RenderedType(
                    "date",
                    imports=frozenset({ImportSpec("datetime", "date")}),
                )
            if schema.format == "time":
                return RenderedType(
                    "time",
                    imports=frozenset({ImportSpec("datetime", "time")}),
                )
            return RenderedType("str")

        if schema_type == "integer":
            return RenderedType("int")
        if schema_type == "number":
            return RenderedType("float")
        if schema_type == "boolean":
            return RenderedType("bool")

        if schema_type == "array":
            if schema.items is None:
                raise GenerationError("array schema must define items")
            item = self.render_type(schema.items)
            return RenderedType(
                expression=f"list[{item.expression}]",
                imports=item.imports,
                model_refs=item.model_refs,
            )

        if schema_type == "object":
            if schema.properties:
                raise GenerationError(
                    "inline object schemas are unsupported; define a named component schema"
                )

            additional = schema.additional_properties
            if isinstance(additional, JSONSchema):
                value = self.render_type(additional)
                return RenderedType(
                    expression=f"dict[str, {value.expression}]",
                    imports=value.imports,
                    model_refs=value.model_refs,
                )
            if additional is False:
                raise GenerationError(
                    "closed object schemas without declared properties are unsupported"
                )

            return RenderedType(
                expression="dict[str, JSONValue]",
                imports=frozenset({ImportSpec("pypokerlost.types", "JSONValue")}),
            )

        raise GenerationError(f"unsupported JSON Schema type: {schema_type!r}")

    def _schema_types(self, schema: JSONSchema) -> list[str]:
        if schema.type is None:
            return []
        if isinstance(schema.type, str):
            return [schema.type]
        return list(schema.type)


class MethodGenerator:
    """Generate one service method package from an OpenAPI document."""

    def __init__(self, document: OpenAPIDocument, source_sha256: str) -> None:
        self.document = document
        self.source_sha256 = source_sha256
        self.resolver = OpenAPIResolver(document)
        self.schemas = SchemaRenderer(self.resolver)

        self.service_id = document.pokerlost_service.id
        self.service_package = PYTHON_PACKAGE_ADAPTER.validate_python(
            to_snake_case(self.service_id)
        )

    def generate(self) -> list[GeneratedFile]:
        operations = self._operation_specs()
        referenced_models = self._referenced_models(operations)
        method_class_names = {operation.class_name for operation in operations}
        generated_names = set(referenced_models) | method_class_names

        reserved_collisions = sorted(generated_names & RESERVED_GENERATED_CLASS_NAMES)
        if reserved_collisions:
            names = ", ".join(reserved_collisions)
            raise GenerationError(f"generated class names conflict with runtime imports: {names}")

        model_method_collisions = sorted(set(referenced_models) & method_class_names)
        if model_method_collisions:
            names = ", ".join(model_method_collisions)
            raise GenerationError(f"generated model and method class names collide: {names}")

        files: list[GeneratedFile] = []

        if referenced_models:
            files.append(
                GeneratedFile(
                    relative_path=Path(self.service_package) / "_models.py",
                    content=self._render_models(referenced_models),
                )
            )

        for operation in operations:
            files.append(
                GeneratedFile(
                    relative_path=Path(self.service_package) / operation.file_name,
                    content=self._render_method(operation),
                )
            )

        files.append(
            GeneratedFile(
                relative_path=Path(self.service_package) / "__init__.py",
                content=self._render_facade(operations, referenced_models),
            )
        )

        return sorted(files, key=lambda item: item.relative_path.as_posix())

    def _operation_specs(self) -> list[OperationSpec]:
        operations: list[OperationSpec] = []
        seen_ids: set[str] = set()
        seen_classes: set[str] = set()
        seen_files: set[str] = set()

        for path in sorted(self.document.paths):
            if path in SYSTEM_PATHS:
                continue

            path_item = self.document.paths[path]
            if path_item.parameters:
                raise GenerationError(
                    f"path-level parameters are unsupported for RPC generation: {path}"
                )

            operations_by_method: tuple[
                tuple[HTTPMethod, OpenAPIOperation | None],
                ...,
            ] = (
                ("DELETE", path_item.delete),
                ("GET", path_item.get),
                ("PATCH", path_item.patch),
                ("POST", path_item.post),
                ("PUT", path_item.put),
            )
            for http_method, operation in operations_by_method:
                if operation is None or operation.deprecated:
                    continue

                raw_operation_id = operation.operation_id
                if raw_operation_id is None:
                    raise GenerationError(f"{http_method} {path} is missing operationId")

                try:
                    operation_id = RPC_OPERATION_ADAPTER.validate_python(raw_operation_id)
                except ValidationError as error:
                    raise GenerationError(
                        f"{http_method} {path} has invalid RPC operationId "
                        f"{raw_operation_id!r}: expected lowercase namespace.method"
                    ) from error

                if operation_id in seen_ids:
                    raise GenerationError(f"duplicate operationId: {operation_id}")
                seen_ids.add(operation_id)

                if path != f"/{operation_id}":
                    raise GenerationError(
                        f"RPC path must exactly match operationId: {path!r} != '/{operation_id}'"
                    )

                if operation.parameters:
                    parameter_list = ", ".join(
                        f"{parameter.location}:{parameter.name}"
                        for parameter in operation.parameters
                    )
                    raise GenerationError(
                        f"{operation_id} uses unsupported OpenAPI parameters: {parameter_list}"
                    )

                request_schema, request_ref = self._request_schema(operation)
                result_schema = self._result_schema(operation, operation_id)

                class_name = self._method_class_name(operation_id, request_ref)
                file_name = f"{to_snake_case(class_name.removesuffix('Method'))}_method.py"

                if class_name in seen_classes:
                    raise GenerationError(f"generated method class collision: {class_name}")
                if file_name in seen_files:
                    raise GenerationError(f"generated method file collision: {file_name}")

                seen_classes.add(class_name)
                seen_files.add(file_name)

                operations.append(
                    OperationSpec(
                        path=path,
                        http_method=http_method,
                        operation_id=operation_id,
                        class_name=class_name,
                        file_name=file_name,
                        request_schema=request_schema,
                        result_schema=result_schema,
                    )
                )

        if not operations:
            raise GenerationError("OpenAPI document contains no non-system RPC operations")

        return sorted(operations, key=lambda item: item.operation_id)

    def _request_schema(
        self,
        operation: OpenAPIOperation,
    ) -> tuple[JSONSchema | None, str | None]:
        if operation.request_body is None:
            return None, None

        body = self.resolver.resolve_request_body(operation.request_body)
        unsupported_content = sorted(set(body.content) - {"application/json"})
        if unsupported_content:
            content_types = ", ".join(unsupported_content)
            raise GenerationError(
                f"RPC requestBody contains unsupported media types: {content_types}"
            )
        media = body.content.get("application/json")
        if media is None or media.schema_ is None:
            raise GenerationError("RPC requestBody must define application/json schema")

        request_schema = media.schema_
        request_ref = (
            self.resolver.schema_ref_name(request_schema.ref)
            if request_schema.ref is not None
            else None
        )

        resolved = self.resolver.resolve_schema(request_schema)
        if resolved.all_of:
            resolved = self.schemas.merge_all_of(resolved)

        schema_types = self._schema_types(resolved)
        if schema_types and any(item not in {"object", "null"} for item in schema_types):
            raise GenerationError("RPC request body must be an object schema")

        if not resolved.properties and resolved.additional_properties is not False:
            raise GenerationError(
                "free-form request bodies are unsupported; declare typed request fields"
            )

        return resolved, request_ref

    def _result_schema(
        self,
        operation: OpenAPIOperation,
        operation_id: GeneratedRPCOperation,
    ) -> JSONSchema:
        success_responses: list[tuple[int, JSONSchema]] = []

        for status, response_node in operation.responses.items():
            if not status.isdigit():
                continue
            status_code = int(status)
            if not 200 <= status_code < 300:
                continue

            response = self.resolver.resolve_response(response_node)
            unsupported_content = sorted(set(response.content) - {"application/json"})
            if unsupported_content:
                content_types = ", ".join(unsupported_content)
                raise GenerationError(
                    f"{operation_id} success response {status} "
                    f"contains unsupported media types: {content_types}"
                )
            media = response.content.get("application/json")
            if media is None or media.schema_ is None:
                raise GenerationError(
                    f"{operation_id} success response {status} must define application/json schema"
                )
            success_responses.append((status_code, media.schema_))

        if not success_responses:
            raise GenerationError(f"{operation_id} has no JSON 2xx success response")

        success_responses.sort(key=lambda item: item[0])
        canonical = {canonical_schema_json(schema) for _, schema in success_responses}
        if len(canonical) != 1:
            raise GenerationError(f"{operation_id} has multiple incompatible 2xx response schemas")

        envelope_schema = self.resolver.resolve_schema(success_responses[0][1])
        if envelope_schema.all_of:
            envelope_schema = self.schemas.merge_all_of(envelope_schema)

        self._validate_application_response_schema(
            operation_id,
            envelope_schema,
        )

        return strip_application_response_null(envelope_schema.properties["result"])

    def _validate_application_response_schema(
        self,
        operation_id: str,
        schema: JSONSchema,
    ) -> None:
        if self.schemas.value_kinds(schema) != {"object"}:
            raise GenerationError(
                f"{operation_id} success response must be an ApplicationResponse object"
            )

        actual_fields = frozenset(schema.properties)
        if actual_fields != APPLICATION_RESPONSE_FIELDS:
            raise GenerationError(
                f"{operation_id} success response fields do not match ApplicationResponse"
            )

        required_fields = frozenset(schema.required)
        if not APPLICATION_RESPONSE_REQUIRED_FIELDS.issubset(required_fields):
            raise GenerationError(
                f"{operation_id} success response omits required ApplicationResponse fields"
            )
        if schema.additional_properties is not False:
            raise GenerationError(
                f"{operation_id} success response must forbid fields outside ApplicationResponse"
            )

        if self.schemas.value_kinds(schema.properties["ok"]) != {"boolean"}:
            raise GenerationError(
                f"{operation_id} success response has incompatible ApplicationResponse.ok"
            )

        error_kinds = {"string", "null"}
        for field_name in ("error", "error_message"):
            kinds = self.schemas.value_kinds(schema.properties[field_name])
            if not kinds or not kinds.issubset(error_kinds):
                raise GenerationError(
                    f"{operation_id} success response has incompatible "
                    f"ApplicationResponse.{field_name}"
                )

    def _method_class_name(self, operation_id: str, request_ref: str | None) -> str:
        if request_ref is not None and request_ref.endswith("Request"):
            semantic = request_ref.removesuffix("Request")
            if semantic:
                try:
                    validated_semantic = PYTHON_CLASS_ADAPTER.validate_python(semantic)
                except ValidationError:
                    validated_semantic = None
                else:
                    return PYTHON_CLASS_ADAPTER.validate_python(f"{validated_semantic}Method")

        semantic = operation_id.rsplit(".", maxsplit=1)[-1]
        return f"{to_pascal_case(semantic)}Method"

    def _referenced_models(
        self,
        operations: Sequence[OperationSpec],
    ) -> list[str]:
        refs: set[str] = set()

        for operation in operations:
            if operation.request_schema is not None:
                for property_schema in operation.request_schema.properties.values():
                    refs.update(self.schemas.collect_refs(property_schema))
            refs.update(self.schemas.collect_refs(operation.result_schema))

        expanded = set(refs)
        pending = list(refs)
        while pending:
            name = pending.pop()
            schema = self.document.components.schemas[name]
            nested = self.schemas.collect_refs(schema)
            for ref in nested:
                if ref not in expanded:
                    expanded.add(ref)
                    pending.append(ref)

        return sorted(expanded)

    def _render_models(self, model_names: Sequence[str]) -> str:
        imports: set[ImportSpec] = {
            ImportSpec("pydantic", "BaseModel"),
            ImportSpec("pydantic", "ConfigDict"),
        }
        model_blocks: list[str] = []
        class_names: list[str] = []

        for name in model_names:
            name = PYTHON_CLASS_ADAPTER.validate_python(name)
            schema = self.document.components.schemas[name]
            block, block_imports, is_class = self._render_component(name, schema)
            imports.update(block_imports)
            model_blocks.append(block)
            if is_class:
                class_names.append(name)

        import_text = render_imports(imports)
        header = self._generated_header()

        base = (
            "class _GeneratedModel(BaseModel):\n"
            "    model_config = ConfigDict(\n"
            '        extra="forbid",\n'
            "        frozen=True,\n"
            "        strict=True,\n"
            "        validate_default=True,\n"
            "    )"
        )

        rebuild = ""
        if class_names:
            rebuild = "\n\n\n" + "\n".join(f"{name}.model_rebuild()" for name in class_names)

        definitions = [base, *model_blocks]
        if ImportSpec("pydantic", "BeforeValidator") in imports:
            definitions.insert(0, EXPLICIT_NULL_REJECTOR_SOURCE)

        return (
            f"{header}\n"
            "from __future__ import annotations\n\n"
            f"{import_text}\n\n\n"
            f"{'\n\n\n'.join(definitions)}"
            f"{rebuild}\n"
        )

    def _render_component(
        self,
        name: str,
        schema: JSONSchema,
    ) -> tuple[str, set[ImportSpec], bool]:
        resolved = self.resolver.resolve_schema(schema)
        if resolved.all_of:
            resolved = self.schemas.merge_all_of(resolved)

        schema_types = self._schema_types(resolved)
        is_object_model = bool(resolved.properties) or "object" in schema_types

        if is_object_model and resolved.properties:
            lines = [f"class {name}(_GeneratedModel):"]
            imports: set[ImportSpec] = set()

            if resolved.description:
                lines.append(f'    """{escape_docstring(resolved.description)}"""')
                lines.append("")

            required = set(resolved.required)
            for field_name, field_schema in sorted(resolved.properties.items()):
                field_line, field_imports = self._render_field(
                    field_name,
                    field_schema,
                    required=field_name in required,
                    import_model_refs=False,
                )
                imports.update(field_imports)
                lines.append(f"    {field_line}")

            return "\n".join(lines), imports, True

        rendered = self.schemas.render_type(resolved)
        return (
            f"type {name} = {rendered.expression}",
            set(rendered.imports),
            False,
        )

    def _render_method(self, operation: OperationSpec) -> str:
        imports: set[ImportSpec] = {
            ImportSpec("pypokerlost.methods", "PokerlostMethod"),
        }

        result_type = self.schemas.render_type(operation.result_schema)
        imports.update(result_type.imports)
        imports.update(
            ImportSpec(f".{self.service_package}._models", name) for name in result_type.model_refs
        )

        fields: list[str] = []
        if operation.request_schema is not None:
            required = set(operation.request_schema.required)
            for field_name, field_schema in sorted(operation.request_schema.properties.items()):
                field_line, field_imports = self._render_field(
                    field_name,
                    field_schema,
                    required=field_name in required,
                )
                imports.update(field_imports)
                fields.append(f"    {field_line}")

        model_imports = {
            item for item in imports if item.module.startswith(f".{self.service_package}._models")
        }
        imports.difference_update(model_imports)

        normalized_imports = {
            ImportSpec("._models", item.name) if item in model_imports else item
            for item in (*imports, *model_imports)
        }

        lines = [
            self._generated_header(),
            "from __future__ import annotations",
            "",
            render_imports(normalized_imports),
        ]

        if ImportSpec("pydantic", "BeforeValidator") in normalized_imports:
            lines.extend(("", "", EXPLICIT_NULL_REJECTOR_SOURCE))

        lines.extend(
            (
                "",
                "",
                f"class {operation.class_name}(PokerlostMethod[{result_type.expression}]):",
                f'    __api_method__ = "{operation.operation_id}"',
                f"    __returning__ = {result_type.expression}",
            )
        )

        if operation.http_method != "POST":
            lines.append(f'    __http_method__ = "{operation.http_method}"')

        if fields:
            lines.append("")
            lines.extend(fields)

        return "\n".join(lines) + "\n"

    def _render_field(
        self,
        name: str,
        schema: JSONSchema,
        *,
        required: bool,
        import_model_refs: bool = True,
    ) -> tuple[str, set[ImportSpec]]:
        rendered = self.schemas.render_type(schema)
        imports = set(rendered.imports)
        if import_model_refs:
            imports.update(ImportSpec("._models", ref) for ref in rendered.model_refs)

        constraints = self.schemas.field_constraints(schema)
        default_present = "default" in schema.model_fields_set

        if required:
            if constraints:
                imports.add(ImportSpec("pydantic", "Field"))
                return render_field_assignment(name, rendered.expression, constraints), imports
            return f"{name}: {rendered.expression}", imports

        if default_present:
            default = schema.default
            if constraints:
                imports.add(ImportSpec("pydantic", "Field"))
                kwargs = {"default": default, **constraints}
                return render_field_assignment(name, rendered.expression, kwargs), imports
            return f"{name}: {rendered.expression} = {python_literal(default)}", imports

        if "None" in rendered.expression.split(" | "):
            if constraints:
                imports.add(ImportSpec("pydantic", "Field"))
                kwargs = {"default": None, **constraints}
                return render_field_assignment(name, rendered.expression, kwargs), imports
            return f"{name}: {rendered.expression} = None", imports

        # The default represents omission and skips validation. Explicit null still
        # reaches the Pydantic validator and is rejected.
        imports.update(
            {
                ImportSpec("pydantic", "BeforeValidator"),
                ImportSpec("pydantic", "Field"),
                ImportSpec("typing", "Annotated"),
            }
        )
        kwargs = {
            "default": None,
            "validate_default": False,
            **constraints,
        }
        field_type = (
            f"Annotated[{rendered.expression} | None, BeforeValidator(_reject_explicit_null)]"
        )
        return render_field_assignment(name, field_type, kwargs), imports

    def _render_facade(
        self,
        operations: Sequence[OperationSpec],
        model_names: Sequence[str],
    ) -> str:
        imports: set[ImportSpec] = {
            *(ImportSpec("._models", name) for name in model_names),
            *(
                ImportSpec(
                    f".{operation.file_name.removesuffix('.py')}",
                    operation.class_name,
                )
                for operation in operations
            ),
        }

        exports = sorted([*model_names, *(item.class_name for item in operations)])

        lines = [
            self._generated_header(),
            "from __future__ import annotations",
            "",
            render_imports(imports),
            "",
            "__all__ = [",
            *(f'    "{name}",' for name in exports),
            "]",
            "",
        ]

        return "\n".join(lines)

    def _generated_header(self) -> str:
        return (
            "# Generated by scripts/generate_methods.py.\n"
            f"# Generator version: {GENERATOR_VERSION.root}\n"
            f"# OpenAPI service: {self.service_id}\n"
            f"# OpenAPI version: {self.document.info.version.root}\n"
            f"# OpenAPI SHA256: {self.source_sha256}\n"
            "# Do not edit manually."
        )

    def _schema_types(self, schema: JSONSchema) -> list[str]:
        if schema.type is None:
            return []
        return [schema.type] if isinstance(schema.type, str) else list(schema.type)


async def read_openapi_file(path: Path) -> OpenAPIDocument:
    try:
        async with aiofiles.open(path, encoding="utf-8") as stream:
            content = await stream.read()
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"failed to read OpenAPI file {path}: {error}") from error

    try:
        return OpenAPIDocument.model_validate_json(content)
    except ValidationError as error:
        raise GenerationError(
            f"invalid OpenAPI document in {path}: {format_pydantic_error(error)}"
        ) from error


async def fetch_openapi_service(base_url: str, timeout: float) -> OpenAPIDocument:
    url = f"{base_url.rstrip('/')}{OPENAPI_ENDPOINT}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise GenerationError(f"failed to fetch {url}: {error}") from error

    try:
        publication = OPENAPI_PUBLICATION_ADAPTER.validate_json(response.text)
    except ValidationError as error:
        raise GenerationError(
            f"{url} did not return the expected ApplicationResponse OpenAPI envelope: "
            f"{format_pydantic_error(error)}"
        ) from error

    if not publication.ok:
        raise GenerationError(
            f"service refused OpenAPI publication: {publication.error}: {publication.error_message}"
        )

    if publication.result is None:
        raise GenerationError("successful OpenAPI publication did not contain a document")
    return publication.result


async def run(settings: GenerationSettings) -> str:
    if settings.source_kind == "file":
        document = await read_openapi_file(settings.source)
    else:
        document = await fetch_openapi_service(
            str(settings.source),
            settings.timeout,
        )

    try:
        source_sha256 = openapi_sha256(document)
    except UnicodeError as error:
        raise GenerationError("OpenAPI document contains invalid UTF-8 text") from error
    generator = MethodGenerator(document, source_sha256)
    generated = generator.generate()

    manifest_path = MANIFEST_DIRECTORY / f"{generator.service_package}.json"
    previous = await read_manifest(manifest_path)
    if previous is not None and (
        previous.service_id != generator.service_id
        or previous.output_package != generator.service_package
    ):
        raise GenerationError(
            f"generation manifest {manifest_path} belongs to another service; "
            "resolve the service-package naming collision before generation"
        )

    enforce_version_policy(
        previous=previous,
        document=document,
        source_sha256=source_sha256,
        force=settings.force,
    )

    expected_manifest = GenerationManifest(
        generator_version=GENERATOR_VERSION,
        openapi_version=document.info.version,
        source_sha256=source_sha256,
        service_id=generator.service_id,
        output_package=generator.service_package,
        files=tuple(item.relative_path.as_posix() for item in generated),
    )

    if settings.check:
        try:
            differences = await check_generated_state(
                output_root=settings.output,
                generated=generated,
                manifest_path=manifest_path,
                expected_manifest=expected_manifest,
                previous_manifest=previous,
            )
        except (OSError, UnicodeError) as error:
            raise GenerationError(f"failed to inspect generated state: {error}") from error
        if differences:
            message = "\n".join(f"- {item}" for item in differences)
            raise GenerationError(f"generated SDK methods are out of date:\n{message}")
        return (
            f"{generator.service_id}: generated methods are up to date "
            f"(OpenAPI {document.info.version.root})"
        )

    try:
        await write_generated_state(
            output_root=settings.output,
            generated=generated,
            manifest_path=manifest_path,
            manifest=expected_manifest,
            previous_manifest=previous,
            force=settings.force,
        )
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"failed to write generated state: {error}") from error

    return (
        f"Generated {len(generated)} files for {generator.service_id} "
        f"from OpenAPI {document.info.version.root}"
    )


def enforce_version_policy(
    *,
    previous: GenerationManifest | None,
    document: OpenAPIDocument,
    source_sha256: str,
    force: bool,
) -> None:
    if previous is None or force:
        return

    new_version = document.info.version
    comparison = new_version.compare(previous.openapi_version)

    if comparison < 0:
        raise GenerationError(
            "OpenAPI version downgrade is not allowed: "
            f"{previous.openapi_version.root} -> {new_version.root}; use --force intentionally"
        )

    if previous.source_sha256 != source_sha256 and comparison <= 0:
        raise GenerationError(
            "OpenAPI contract changed without a SemVer precedence increase: "
            f"version is still {new_version.root}; bump info.version or use --force intentionally"
        )


async def read_manifest(path: Path) -> GenerationManifest | None:
    try:
        if not await aiofiles.os.path.exists(path):
            return None
        async with aiofiles.open(path, encoding="utf-8") as stream:
            content = await stream.read()
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"failed to read generation manifest {path}: {error}") from error

    try:
        return GenerationManifest.model_validate_json(content)
    except ValidationError as error:
        raise GenerationError(
            f"invalid generation manifest {path}: {format_pydantic_error(error)}"
        ) from error


async def check_generated_state(
    *,
    output_root: Path,
    generated: Sequence[GeneratedFile],
    manifest_path: Path,
    expected_manifest: GenerationManifest,
    previous_manifest: GenerationManifest | None,
) -> list[str]:
    differences: list[str] = []

    expected_paths = {item.relative_path.as_posix() for item in generated}
    previous_paths = set(previous_manifest.files if previous_manifest is not None else ())

    for item in generated:
        target = output_root / item.relative_path
        if not await aiofiles.os.path.exists(target):
            differences.append(f"missing {target}")
            continue

        async with aiofiles.open(target, encoding="utf-8") as stream:
            actual = await stream.read()
        if actual != item.content:
            differences.append(f"changed {target}")

    for stale in sorted(previous_paths - expected_paths):
        target = output_root / stale
        if await aiofiles.os.path.exists(target):
            differences.append(f"stale generated file {target}")

    if not await aiofiles.os.path.exists(manifest_path):
        differences.append(f"missing manifest {manifest_path}")
    else:
        async with aiofiles.open(manifest_path, encoding="utf-8") as stream:
            actual_manifest = await stream.read()
        expected_text = manifest_json(expected_manifest)
        if actual_manifest != expected_text:
            differences.append(f"changed manifest {manifest_path}")

    return differences


async def write_generated_state(
    *,
    output_root: Path,
    generated: Sequence[GeneratedFile],
    manifest_path: Path,
    manifest: GenerationManifest,
    previous_manifest: GenerationManifest | None,
    force: bool,
) -> None:
    await aiofiles.os.makedirs(output_root, exist_ok=True)
    await aiofiles.os.makedirs(manifest_path.parent, exist_ok=True)

    expected_paths = {item.relative_path.as_posix() for item in generated}
    previous_paths = set(previous_manifest.files if previous_manifest is not None else ())

    for item in generated:
        target = output_root / item.relative_path
        await assert_safe_generated_target(target, force=force)

    stale_targets: list[Path] = []
    for stale in sorted(previous_paths - expected_paths):
        target = output_root / stale
        if not await aiofiles.os.path.exists(target):
            continue
        await assert_safe_generated_target(target, force=force)
        stale_targets.append(target)

    for item in generated:
        target = output_root / item.relative_path
        await atomic_write_text(target, item.content)

    for target in stale_targets:
        await aiofiles.os.unlink(target)

    await atomic_write_text(manifest_path, manifest_json(manifest))


async def assert_safe_generated_target(path: Path, *, force: bool) -> None:
    if force or not await aiofiles.os.path.exists(path):
        return

    async with aiofiles.open(path, encoding="utf-8") as stream:
        first_line = await stream.readline()

    if first_line != "# Generated by scripts/generate_methods.py.\n":
        raise GenerationError(
            f"refusing to overwrite non-generated file {path}; use --force only if intentional"
        )


async def atomic_write_text(path: Path, content: str) -> None:
    await aiofiles.os.makedirs(path.parent, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary_created = False

    try:
        async with aiofiles.open(temporary, "x", encoding="utf-8", newline="\n") as stream:
            temporary_created = True
            await stream.write(content)
        await aiofiles.os.replace(temporary, path)
    finally:
        if temporary_created and await aiofiles.os.path.exists(temporary):
            await aiofiles.os.unlink(temporary)


def openapi_sha256(document: OpenAPIDocument) -> str:
    canonical = json.dumps(
        document.model_dump(
            mode="json",
            by_alias=True,
            exclude_unset=True,
        ),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def canonical_schema_json(schema: JSONSchema) -> str:
    return json.dumps(
        schema.model_dump(
            mode="json",
            by_alias=True,
            exclude_unset=True,
        ),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def manifest_json(manifest: GenerationManifest) -> str:
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def render_imports(imports: Iterable[ImportSpec]) -> str:
    grouped: dict[int, dict[str, list[str]]] = {}

    for item in sorted(set(imports)):
        group = import_group(item.module)
        grouped.setdefault(group, {}).setdefault(item.module, []).append(item.name)

    sections: list[str] = []
    for group in sorted(grouped):
        lines: list[str] = []
        for module, names in sorted(grouped[group].items()):
            unique_names = sorted(set(names))
            single_line = f"from {module} import {', '.join(unique_names)}"
            if len(single_line) <= 100:
                lines.append(single_line)
                continue

            lines.extend(
                [
                    f"from {module} import (",
                    *(f"    {name}," for name in unique_names),
                    ")",
                ]
            )
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def import_group(module: str) -> int:
    if module in {"datetime", "typing", "uuid"}:
        return 0
    if module == "pydantic" or module.startswith("pydantic."):
        return 1
    if module.startswith("pypokerlost"):
        return 2
    if module.startswith("."):
        return 3
    return 1


def strip_application_response_null(schema: JSONSchema) -> JSONSchema:
    """Remove the envelope-level null added by ApplicationResponse[ResultT]."""
    if schema.any_of:
        non_null = [item for item in schema.any_of if not schema_is_null(item)]
        if not non_null:
            return JSONSchema(type="null")
        if len(non_null) == 1:
            return non_null[0]
        return JSONSchema(any_of=non_null)

    if schema.one_of:
        non_null = [item for item in schema.one_of if not schema_is_null(item)]
        if not non_null:
            return JSONSchema(type="null")
        if len(non_null) == 1:
            return non_null[0]
        return JSONSchema(one_of=non_null)

    if isinstance(schema.type, list) and "null" in schema.type:
        concrete = [item for item in schema.type if item != "null"]
        if not concrete:
            return JSONSchema(type="null")
        return schema.model_copy(update={"type": concrete[0] if len(concrete) == 1 else concrete})

    return schema


def schema_is_null(schema: JSONSchema) -> bool:
    if schema.ref is not None:
        return False
    if schema.type == "null":
        return True
    if isinstance(schema.type, list):
        return schema.type == ["null"]
    return False


def render_keyword_arguments(values: dict[str, JSONValue]) -> str:
    return ", ".join(f"{name}={python_literal(value)}" for name, value in values.items())


def render_field_assignment(
    name: str,
    annotation: str,
    keyword_arguments: dict[str, JSONValue],
) -> str:
    rendered_arguments = [
        f"{argument_name}={python_literal(value)}"
        for argument_name, value in keyword_arguments.items()
    ]
    single_line = f"{name}: {annotation} = Field({', '.join(rendered_arguments)})"
    if len(single_line) + 4 <= 100:
        return single_line

    return "\n".join(
        (
            f"{name}: {annotation} = Field(",
            *(f"        {argument}," for argument in rendered_arguments),
            "    )",
        )
    )


def python_literal(value: JSONValue) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float, bool)) or value is None:
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(python_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(
                f"{python_literal(key)}: {python_literal(item)}"
                for key, item in sorted(value.items())
            )
            + "}"
        )
    raise GenerationError(f"unsupported JSON Schema default value: {value!r}")


def to_pascal_case(value: str) -> PythonClassName:
    parts = [item for item in re.split(r"[^A-Za-z0-9]+", value) if item]
    if not parts:
        raise GenerationError(f"cannot derive a Python class name from {value!r}")

    result = "".join(
        PASCAL_CASE_ACRONYMS.get(item.lower(), item[:1].upper() + item[1:]) for item in parts
    )
    try:
        return PYTHON_CLASS_ADAPTER.validate_python(result)
    except ValidationError as error:
        raise GenerationError(f"cannot derive a valid Python class name from {value!r}") from error


def to_snake_case(value: str) -> str:
    acronyms = set(PASCAL_CASE_ACRONYMS.values())
    acronym_pattern = "|".join(
        re.escape(acronym) for acronym in sorted(acronyms, key=len, reverse=True)
    )
    tokens: list[str] = []

    for segment in re.split(f"({acronym_pattern})", value):
        if not segment:
            continue
        if segment in acronyms:
            tokens.append(segment.lower())
            continue

        normalized = re.sub(r"[^A-Za-z0-9]+", "_", segment)
        normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", normalized)
        normalized = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", normalized)
        tokens.extend(item.lower() for item in normalized.split("_") if item)

    return "_".join(tokens)


def escape_docstring(value: str) -> str:
    normalized = " ".join(value.split())
    return normalized.replace("\\", "\\\\").replace('"""', r"\"\"\"")


app = typer.Typer(
    name="generate-methods",
    help="Generate typed Pokerlost SDK methods from OpenAPI 3.1 contracts.",
    epilog=(
        "Generated sources are deterministic and protected by a versioned manifest. "
        "Use `--check` in CI to verify that committed methods match the contract."
    ),
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    rich_markup_mode="markdown",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def show_version(value: bool) -> None:
    """Print the generator version before command dispatch."""
    if not value:
        return
    typer.echo(GENERATOR_VERSION.root)
    raise typer.Exit()


@app.callback()
def cli(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=show_version,
            is_eager=True,
            help="Show the generator version and exit.",
        ),
    ] = False,
) -> None:
    """Generate deterministic SDK methods from one service contract."""


@app.command("file", rich_help_panel="Contract sources")
def generate_from_file(
    source: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="OpenAPI 3.1 JSON document.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            file_okay=False,
            dir_okay=True,
            help="Generated methods package root.",
            show_default=True,
        ),
    ] = DEFAULT_OUTPUT,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Verify generated files without writing changes.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Allow intentional overwrite and version-policy bypass.",
        ),
    ] = False,
) -> None:
    """Generate methods from a local raw OpenAPI JSON document."""
    execute_command(
        {
            "source_kind": "file",
            "source": source,
            "output": output,
            "check": check,
            "force": force,
        }
    )


@app.command("service", rich_help_panel="Contract sources")
def generate_from_service(
    source: Annotated[
        str,
        typer.Argument(
            help=(f"Pokerlost service base URL. The contract is read from {OPENAPI_ENDPOINT}."),
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            file_okay=False,
            dir_okay=True,
            help="Generated methods package root.",
            show_default=True,
        ),
    ] = DEFAULT_OUTPUT,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Verify generated files without writing changes.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Allow intentional overwrite and version-policy bypass.",
        ),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="OpenAPI request timeout in seconds.",
            show_default=True,
        ),
    ] = 10.0,
) -> None:
    """Fetch `/openapi.get` from a running Pokerlost service and generate methods."""
    execute_command(
        {
            "source_kind": "service",
            "source": source,
            "output": output,
            "check": check,
            "force": force,
            "timeout": timeout,
        }
    )


def execute_command(values: dict[str, Any]) -> None:
    """Validate one Typer command and execute generation with clean failures."""
    try:
        settings = GENERATION_SETTINGS_ADAPTER.validate_python(values)
        message = asyncio.run(run(settings))
    except ValidationError as error:
        fail_cli(format_pydantic_error(error))
    except GenerationError as error:
        fail_cli(str(error))
    else:
        typer.secho(message, fg=typer.colors.GREEN)


def format_pydantic_error(error: ValidationError) -> str:
    """Render Pydantic validation without tracebacks or implementation noise."""
    messages: list[str] = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"])
        prefix = f"{location}: " if location else ""
        messages.append(f"{prefix}{item['msg']}")
    return "; ".join(messages)


def fail_cli(message: str) -> Never:
    """Print one domain error and stop command execution."""
    typer.secho(
        f"Error: {message}",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
