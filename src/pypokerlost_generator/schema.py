"""Pure OpenAPI validation, schema resolution and global collection."""

from __future__ import annotations

import hashlib
import json
import keyword
import math
from collections.abc import Mapping, Sequence
from functools import cache

from pydantic import PydanticSchemaGenerationError, TypeAdapter

from pypokerlost.types import PokerlostOperation
from pypokerlost_generator.models import (
    CANONICAL_SCHEMA_TYPES,
    CANONICAL_TYPES,
    ENVELOPE_FIELDS,
    INFRASTRUCTURE_GET_OPERATIONS,
    POKERLOST_SECURITY_SCHEME,
    PYTHON_NAME_PATTERN,
    SCOPE_PATTERN,
    SDK_SCOPE_VALUES,
    SEMVER_PATTERN,
    GenerationError,
    OperationSpec,
    SourceDocument,
    TypeSpec,
    to_snake_case,
)


def _mapping(value: object, *, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GenerationError(f"{location} must be an object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if type(key) is not str:
            raise GenerationError(f"{location} must use string keys")
        result[key] = item
    return result


def _sequence(value: object, *, location: str) -> list[object]:
    if not isinstance(value, list):
        raise GenerationError(f"{location} must be an array")
    return list(value)


def _string(value: object, *, location: str) -> str:
    if type(value) is not str or not value:
        raise GenerationError(f"{location} must be a non-empty string")
    return value


def _optional_mapping(
    parent: Mapping[str, object],
    name: str,
    *,
    location: str,
) -> dict[str, object]:
    value = parent.get(name)
    if value is None:
        return {}
    return _mapping(value, location=f"{location}.{name}")


def _json_object(text: str, *, location: str) -> dict[str, object]:
    try:
        decoded: object = json.loads(text)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise GenerationError(f"{location} is not valid JSON") from error
    return _mapping(decoded, location=location)


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError) as error:
        raise GenerationError("OpenAPI contains a non-JSON value") from error


_SCHEMA_ANNOTATION_KEYS = frozenset(
    {
        "$defs",
        "default",
        "deprecated",
        "description",
        "examples",
        "title",
    }
)


_ORDER_INSENSITIVE_SCHEMA_ARRAYS = frozenset(
    {
        "allOf",
        "anyOf",
        "enum",
        "oneOf",
        "required",
    }
)


def _normalize_schema_contract(value: object) -> object:
    """Remove documentation-only variance while preserving wire constraints."""
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_normalize_schema_contract(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized: dict[str, object] = {}
    for raw_key, child in value.items():
        if type(raw_key) is not str:
            raise GenerationError("JSON Schema contract must use string keys")
        if raw_key in _SCHEMA_ANNOTATION_KEYS:
            continue
        normalized_child = _normalize_schema_contract(child)
        if raw_key in _ORDER_INSENSITIVE_SCHEMA_ARRAYS:
            if not isinstance(normalized_child, list):
                raise GenerationError(f"JSON Schema {raw_key} must be an array")
            normalized_child = sorted(normalized_child, key=_canonical_json)
        normalized[raw_key] = normalized_child
    return normalized


@cache
def _sdk_canonical_schema_contract(name: str) -> str:
    """Return the normalized SDK-owned contract for one canonical wire type."""
    schema_type = CANONICAL_SCHEMA_TYPES[name]
    try:
        generated: object = TypeAdapter(schema_type).json_schema(
            ref_template="#/components/schemas/{model}"
        )
    except (TypeError, ValueError, PydanticSchemaGenerationError) as error:
        raise GenerationError(f"SDK canonical schema {name} cannot be inspected") from error
    root = _mapping(generated, location=f"SDK canonical schema {name}")
    definitions = _optional_mapping(root, "$defs", location=f"SDK canonical schema {name}")
    without_definitions = dict(root)
    without_definitions.pop("$defs", None)
    expected_reference = f"#/components/schemas/{name}"
    if without_definitions == {"$ref": expected_reference}:
        definition = definitions.get(name)
        if definition is None:
            raise GenerationError(f"SDK canonical schema {name} has no root definition")
        without_definitions = _schema(
            definition,
            location=f"SDK canonical schema {name} definition",
        )
    return _canonical_json(_normalize_schema_contract(without_definitions))


def _reject_extensions(value: object, *, location: str) -> None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            if type(raw_key) is not str:
                raise GenerationError(f"{location} must use string keys")
            if raw_key.startswith("x-"):
                raise GenerationError(f"{location}.{raw_key} uses a forbidden vendor extension")
            _reject_extensions(child, location=f"{location}.{raw_key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_extensions(child, location=f"{location}[{index}]")


def _scope_value(value: object, *, location: str) -> str:
    scope = _string(value, location=location)
    if SCOPE_PATTERN.fullmatch(scope) is None:
        raise GenerationError(f"{location} must contain dotted lowerCamelCase segments")
    return scope


def _oauth2_catalog(
    security_schemes: dict[str, object],
    *,
    label: str,
) -> tuple[str | None, dict[str, str]]:
    if not security_schemes:
        return None, {}
    if len(security_schemes) != 1:
        raise GenerationError(f"{label} must publish exactly one Pokerlost OAuth2 scheme")
    scheme_name, raw_scheme = next(iter(security_schemes.items()))
    if scheme_name != POKERLOST_SECURITY_SCHEME:
        raise GenerationError(
            f"{label} OAuth2 security scheme must be named {POKERLOST_SECURITY_SCHEME}"
        )
    scheme = _mapping(raw_scheme, location=f"{label}.components.securitySchemes.{scheme_name}")
    if scheme.get("type") != "oauth2":
        raise GenerationError(f"{label} security scheme must use OAuth2")
    allowed_scheme_fields = {"type", "description", "flows"}
    if set(scheme) - allowed_scheme_fields:
        raise GenerationError(f"{label} OAuth2 scheme contains unsupported fields")
    flows = _mapping(scheme.get("flows"), location=f"{label}.{scheme_name}.flows")
    if set(flows) != {"clientCredentials"}:
        raise GenerationError(f"{label} OAuth2 scheme must use only clientCredentials flow")
    client_credentials = _mapping(
        flows["clientCredentials"],
        location=f"{label}.{scheme_name}.flows.clientCredentials",
    )
    if set(client_credentials) != {"scopes", "tokenUrl"}:
        raise GenerationError(f"{label} clientCredentials flow contains unsupported fields")
    if client_credentials.get("tokenUrl") != "/getToken":
        raise GenerationError(f"{label} OAuth2 tokenUrl must equal /getToken")
    raw_scopes = _mapping(
        client_credentials.get("scopes"),
        location=f"{label}.{scheme_name}.flows.clientCredentials.scopes",
    )
    scopes: dict[str, str] = {}
    for raw_scope, raw_description in sorted(raw_scopes.items()):
        scope = _scope_value(raw_scope, location=f"{label}.{scheme_name}.scopes")
        description = _string(
            raw_description,
            location=f"{label}.{scheme_name}.scopes.{scope}",
        )
        scopes[scope] = description
    return scheme_name, scopes


def parse_document(raw: dict[str, object], *, label: str) -> SourceDocument:
    """Validate document-level OpenAPI invariants without service identity metadata."""
    _reject_extensions(raw, location=label)
    openapi = _string(raw.get("openapi"), location=f"{label}.openapi")
    if not openapi.startswith("3.1."):
        raise GenerationError(f"{label} must use OpenAPI 3.1.x")
    info = _mapping(raw.get("info"), location=f"{label}.info")
    title = _string(info.get("title"), location=f"{label}.info.title")
    version = _string(info.get("version"), location=f"{label}.info.version")
    if SEMVER_PATTERN.fullmatch(version) is None:
        raise GenerationError(f"{label}.info.version must be SemVer")
    paths = _mapping(raw.get("paths"), location=f"{label}.paths")
    components = _optional_mapping(raw, "components", location=label)
    schemas = _optional_mapping(components, "schemas", location=f"{label}.components")
    security_schemes = _optional_mapping(
        components,
        "securitySchemes",
        location=f"{label}.components",
    )
    if _sequence(raw.get("security", []), location=f"{label}.security"):
        raise GenerationError(f"{label} must not publish document-level OpenAPI security")
    security_scheme, scopes = _oauth2_catalog(security_schemes, label=label)
    source_sha256 = hashlib.sha256(_canonical_json(raw).encode()).hexdigest()
    return SourceDocument(
        label=f"{title} ({label})",
        title=title,
        version=version,
        source_sha256=source_sha256,
        paths=paths,
        schemas=schemas,
        security_scheme=security_scheme,
        scopes=scopes,
    )


def _reference_name(reference: str, *, location: str) -> str:
    prefix = "#/components/schemas/"
    if not reference.startswith(prefix):
        raise GenerationError(f"{location} must use a local component schema reference")
    name = reference.removeprefix(prefix)
    if not name or "/" in name or "~" in name:
        raise GenerationError(f"{location} contains an invalid component reference")
    return name


def _track_canonical_references(
    value: object,
    source: SourceDocument,
    *,
    canonical_schemas: dict[str, tuple[SourceDocument, str]],
    location: str,
    seen: frozenset[str] = frozenset(),
) -> None:
    """Compare every canonical schema reachable from a business operation."""
    if isinstance(value, list):
        for index, child in enumerate(value):
            _track_canonical_references(
                child,
                source,
                canonical_schemas=canonical_schemas,
                location=f"{location}[{index}]",
                seen=seen,
            )
        return
    if not isinstance(value, dict):
        return
    reference_value = value.get("$ref")
    if reference_value is not None:
        reference = _reference_name(
            _string(reference_value, location=f"{location}.$ref"),
            location=f"{location}.$ref",
        )
        component = source.schemas.get(reference)
        if component is None:
            raise GenerationError(f"{location} references unknown schema {reference!r}")
        component_schema = _schema(
            component,
            location=f"{source.label}.components.schemas.{reference}",
        )
        if reference in CANONICAL_TYPES:
            serialized = _canonical_json(_normalize_schema_contract(component_schema))
            if serialized != _sdk_canonical_schema_contract(reference):
                raise GenerationError(
                    f"canonical schema {reference} does not match the SDK-owned contract"
                )
            previous = canonical_schemas.get(reference)
            if previous is not None and previous[1] != serialized:
                raise GenerationError(
                    f"global canonical schema collision for {reference}: "
                    f"{previous[0].label} and {source.label}"
                )
            canonical_schemas.setdefault(reference, (source, serialized))
        if reference in seen:
            return
        _track_canonical_references(
            component_schema,
            source,
            canonical_schemas=canonical_schemas,
            location=f"{source.label}.components.schemas.{reference}",
            seen=seen | {reference},
        )
        return
    for key, child in value.items():
        _track_canonical_references(
            child,
            source,
            canonical_schemas=canonical_schemas,
            location=f"{location}.{key}",
            seen=seen,
        )


def _schema(value: object, *, location: str) -> dict[str, object]:
    return _mapping(value, location=location)


def _resolve_schema(
    schema: dict[str, object],
    source: SourceDocument,
    *,
    location: str,
    seen: frozenset[str] = frozenset(),
) -> dict[str, object]:
    reference = schema.get("$ref")
    if reference is not None:
        reference_value = _string(reference, location=f"{location}.$ref")
        name = _reference_name(reference_value, location=f"{location}.$ref")
        if name in seen:
            raise GenerationError(f"{location} contains a recursive envelope schema")
        component = source.schemas.get(name)
        if component is None:
            raise GenerationError(f"{location} references unknown schema {name!r}")
        return _resolve_schema(
            _schema(component, location=f"{source.label}.components.schemas.{name}"),
            source,
            location=f"{source.label}.components.schemas.{name}",
            seen=seen | {name},
        )
    all_of = schema.get("allOf")
    if all_of is None:
        return schema
    branches = _sequence(all_of, location=f"{location}.allOf")
    merged_properties: dict[str, object] = {}
    merged_required: list[object] = []
    for index, branch in enumerate(branches):
        resolved = _resolve_schema(
            _schema(branch, location=f"{location}.allOf[{index}]"),
            source,
            location=f"{location}.allOf[{index}]",
            seen=seen,
        )
        properties = _optional_mapping(resolved, "properties", location=location)
        duplicate = sorted(set(merged_properties).intersection(properties))
        if duplicate:
            raise GenerationError(f"{location}.allOf repeats object fields: {', '.join(duplicate)}")
        merged_properties.update(properties)
        required = resolved.get("required", [])
        merged_required.extend(_sequence(required, location=f"{location}.required"))
    return {
        "type": "object",
        "properties": merged_properties,
        "required": merged_required,
        "additionalProperties": False,
    }


def _object_properties(
    schema: dict[str, object],
    source: SourceDocument,
    *,
    location: str,
) -> tuple[dict[str, object], frozenset[str]]:
    resolved = _resolve_schema(schema, source, location=location)
    properties = _optional_mapping(resolved, "properties", location=location)
    required_values = _sequence(resolved.get("required", []), location=f"{location}.required")
    required: set[str] = set()
    for item in required_values:
        required.add(_string(item, location=f"{location}.required[]"))
    if set(required) - set(properties):
        raise GenerationError(f"{location} requires unknown object fields")
    if resolved.get("additionalProperties") is not False:
        raise GenerationError(f"{location} must forbid undeclared object fields")
    return properties, frozenset(required)


def _request_envelope(
    operation: PokerlostOperation,
    raw_operation: dict[str, object],
    source: SourceDocument,
) -> dict[str, object]:
    body = _mapping(raw_operation.get("requestBody"), location=f"{operation}.requestBody")
    if body.get("required") is not True:
        raise GenerationError(f"{operation} requestBody must be required")
    content = _mapping(body.get("content"), location=f"{operation}.requestBody.content")
    if set(content) != {"application/json"}:
        raise GenerationError(f"{operation} must accept exactly application/json")
    media = _mapping(content["application/json"], location=f"{operation}.requestBody.content")
    envelope_schema = _schema(media.get("schema"), location=f"{operation}.requestBody.schema")
    properties, required = _object_properties(
        envelope_schema,
        source,
        location=f"{operation}.requestBody.schema",
    )
    fields = frozenset(properties)
    if fields == {"payload"} and required == {"payload"}:
        return _schema(properties["payload"], location=f"{operation}.payload")
    raise GenerationError(f"{operation} request must use the pure PokerlostRequest envelope")


def _operation_scopes(
    operation: PokerlostOperation,
    raw_operation: dict[str, object],
    source: SourceDocument,
) -> tuple[str, ...] | None:
    security = _sequence(raw_operation.get("security", []), location=f"{operation}.security")
    if not security:
        return None
    if source.security_scheme is None:
        raise GenerationError(
            f"{operation} declares security but its document has no Pokerlost OAuth2 scheme"
        )
    if len(security) != 1:
        raise GenerationError(f"{operation} must not use alternative security requirements")
    requirement = _mapping(security[0], location=f"{operation}.security[0]")
    if set(requirement) != {source.security_scheme}:
        raise GenerationError(f"{operation} references an unknown or mixed security scheme")
    raw_scopes = _sequence(
        requirement[source.security_scheme],
        location=f"{operation}.security.{source.security_scheme}",
    )
    if not raw_scopes:
        raise GenerationError(f"{operation} OAuth2 security scopes must not be empty")
    scopes = tuple(
        _scope_value(value, location=f"{operation}.security.{source.security_scheme}[]")
        for value in raw_scopes
    )
    if len(frozenset(scopes)) != len(scopes):
        raise GenerationError(f"{operation} security scopes must not contain duplicates")
    unknown = sorted(set(scopes) - set(source.scopes))
    if unknown:
        raise GenerationError(f"{operation} uses unknown OAuth2 scopes: {', '.join(unknown)}")
    unknown_sdk_scopes = sorted(set(scopes) - SDK_SCOPE_VALUES)
    if unknown_sdk_scopes:
        raise GenerationError(
            f"{operation} uses scopes absent from PokerlostScopes: " + ", ".join(unknown_sdk_scopes)
        )
    return tuple(sorted(scopes))


def _schema_kinds(schema: dict[str, object]) -> frozenset[str]:
    raw_type = schema.get("type")
    if type(raw_type) is str:
        return frozenset({raw_type})
    if isinstance(raw_type, list):
        kinds: set[str] = set()
        for value in raw_type:
            kinds.add(_string(value, location="schema.type[]"))
        return frozenset(kinds)
    branches = schema.get("anyOf", schema.get("oneOf"))
    if branches is not None:
        branch_kinds: set[str] = set()
        for branch in _sequence(branches, location="schema union"):
            branch_kinds.update(_schema_kinds(_schema(branch, location="schema union branch")))
        return frozenset(branch_kinds)
    if "$ref" in schema:
        return frozenset({"reference"})
    if "properties" in schema:
        return frozenset({"object"})
    return frozenset()


def _strip_null(schema: dict[str, object]) -> dict[str, object]:
    branches_value = schema.get("anyOf", schema.get("oneOf"))
    if branches_value is None:
        if schema.get("type") == "null":
            return {"type": "null"}
        raw_type = schema.get("type")
        if isinstance(raw_type, list):
            remaining = [value for value in raw_type if value != "null"]
            if len(remaining) == 1:
                result = dict(schema)
                result["type"] = remaining[0]
                return result
            if remaining:
                result = dict(schema)
                result["type"] = remaining
                return result
        return schema
    remaining_branches: list[object] = []
    for branch in _sequence(branches_value, location="response.result union"):
        branch_schema = _schema(branch, location="response.result union branch")
        if _schema_kinds(branch_schema) != {"null"}:
            remaining_branches.append(branch_schema)
    if not remaining_branches:
        return {"type": "null"}
    if len(remaining_branches) == 1:
        return _schema(remaining_branches[0], location="response.result")
    return {"anyOf": remaining_branches}


def _response_result(
    operation: PokerlostOperation,
    raw_operation: dict[str, object],
    source: SourceDocument,
) -> dict[str, object]:
    responses = _mapping(raw_operation.get("responses"), location=f"{operation}.responses")
    if not responses:
        raise GenerationError(f"{operation} must document PokerlostResponse bodies")
    success_schemas: list[dict[str, object]] = []
    for status, raw_response in sorted(responses.items()):
        response = _mapping(raw_response, location=f"{operation}.responses.{status}")
        response_headers = _optional_mapping(
            response,
            "headers",
            location=f"{operation}.responses.{status}",
        )
        if response_headers:
            raise GenerationError(f"{operation} response {status} must not declare headers")
        content = _mapping(
            response.get("content"), location=f"{operation}.responses.{status}.content"
        )
        if set(content) != {"application/json"}:
            raise GenerationError(f"{operation} response {status} must contain exactly JSON")
        media = _mapping(content["application/json"], location=f"{operation}.responses.{status}")
        envelope = _resolve_schema(
            _schema(media.get("schema"), location=f"{operation}.responses.{status}.schema"),
            source,
            location=f"{operation}.responses.{status}.schema",
        )
        properties, required = _object_properties(
            envelope,
            source,
            location=f"{operation}.responses.{status}.schema",
        )
        if frozenset(properties) != ENVELOPE_FIELDS:
            raise GenerationError(f"{operation} response {status} must be PokerlostResponse")
        if required != {"ok"}:
            raise GenerationError(f"{operation} response {status} must require exactly ok")
        if _schema_kinds(
            _schema(properties["ok"], location=f"{operation}.responses.{status}.ok")
        ) != {"boolean"}:
            raise GenerationError(f"{operation} response {status} ok field must be boolean")
        for field_name in ("error", "error_message"):
            error_kinds = _schema_kinds(
                _schema(
                    properties[field_name],
                    location=f"{operation}.responses.{status}.{field_name}",
                )
            )
            if not error_kinds or not error_kinds.issubset({"string", "null"}):
                raise GenerationError(
                    f"{operation} response {status} {field_name} must be a string or null"
                )
        retry_kinds = _schema_kinds(
            _schema(
                properties["retry_after"],
                location=f"{operation}.responses.{status}.retry_after",
            )
        )
        if not retry_kinds or not retry_kinds.issubset({"integer", "number", "null"}):
            raise GenerationError(
                f"{operation} response {status} retry_after must be numeric or null"
            )
        result_schema = _schema(
            properties["result"],
            location=f"{operation}.responses.{status}.result",
        )
        if status.isdigit() and 200 <= int(status) < 300:
            success_schemas.append(envelope)
        elif _schema_kinds(result_schema) != {"null"}:
            raise GenerationError(f"{operation} failure response {status} result must be null")
    if not success_schemas:
        raise GenerationError(f"{operation} must define a JSON 2xx response")
    if len({_canonical_json(schema) for schema in success_schemas}) != 1:
        raise GenerationError(f"{operation} has incompatible 2xx response schemas")
    properties, _ = _object_properties(
        success_schemas[0],
        source,
        location=f"{operation}.response",
    )
    return _strip_null(_schema(properties["result"], location=f"{operation}.response.result"))


def collect_operations(documents: Sequence[SourceDocument]) -> tuple[OperationSpec, ...]:
    """Validate all routes and return operations only after global uniqueness holds."""
    operations: list[OperationSpec] = []
    seen: dict[PokerlostOperation, str] = {}
    seen_classes: dict[str, PokerlostOperation] = {}
    seen_modules: dict[str, PokerlostOperation] = {}
    canonical_schemas: dict[str, tuple[SourceDocument, str]] = {}
    for source in documents:
        for path, raw_path_item in sorted(source.paths.items()):
            path_item = _mapping(raw_path_item, location=f"{source.label}.paths.{path}")
            for method_name in (
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
                "trace",
            ):
                raw_operation_value = path_item.get(method_name)
                if raw_operation_value is None:
                    continue
                raw_operation = _mapping(
                    raw_operation_value,
                    location=f"{source.label}.paths.{path}.{method_name}",
                )
                operation_value = _string(
                    raw_operation.get("operationId"),
                    location=f"{source.label}.paths.{path}.{method_name}.operationId",
                )
                try:
                    operation = PokerlostOperation(operation_value)
                except (TypeError, ValueError) as error:
                    raise GenerationError(
                        f"{method_name.upper()} {path} operationId must be single lowerCamelCase"
                    ) from error
                path_parameters = path_item.get("parameters", [])
                operation_parameters = raw_operation.get("parameters", [])
                if method_name == "get" and operation in INFRASTRUCTURE_GET_OPERATIONS:
                    expected_path = "/" if operation == "getRoot" else f"/{operation}"
                    if path != expected_path:
                        raise GenerationError(
                            f"infrastructure path for {operation} must equal {expected_path}"
                        )
                    if _sequence(path_parameters, location=f"{path}.parameters") or _sequence(
                        operation_parameters,
                        location=f"{operation}.parameters",
                    ):
                        raise GenerationError(
                            f"infrastructure operation {operation} must not use parameters"
                        )
                    if raw_operation.get("requestBody") is not None:
                        raise GenerationError(
                            f"infrastructure operation {operation} must not use a request body"
                        )
                    security = raw_operation.get("security", [])
                    if _sequence(security, location=f"{operation}.security"):
                        raise GenerationError(
                            f"infrastructure operation {operation} must be public"
                        )
                    continue
                if method_name != "post":
                    raise GenerationError(f"business operation {operation} must use POST")
                if path != f"/{operation}":
                    raise GenerationError(f"business path must equal /{operation}")
                if _sequence(path_parameters, location=f"{path}.parameters") or _sequence(
                    operation_parameters,
                    location=f"{operation}.parameters",
                ):
                    raise GenerationError(f"{operation} must not use OpenAPI parameters")
                previous = seen.get(operation)
                if previous is not None:
                    raise GenerationError(
                        f"global operation collision for {operation}: {previous} and {source.label}"
                    )
                seen[operation] = source.label
                class_name = operation[0].upper() + operation[1:]
                module_name = to_snake_case(operation)
                previous_class = seen_classes.get(class_name)
                previous_module = seen_modules.get(module_name)
                if previous_class is not None:
                    raise GenerationError(
                        f"global method class collision for {previous_class} and {operation}"
                    )
                if previous_module is not None:
                    raise GenerationError(
                        f"global method module collision for {previous_module} and {operation}"
                    )
                seen_classes[class_name] = operation
                seen_modules[module_name] = operation
                _track_canonical_references(
                    raw_operation,
                    source,
                    canonical_schemas=canonical_schemas,
                    location=f"{source.label}.paths.{path}.{method_name}",
                )
                payload_schema = _request_envelope(operation, raw_operation, source)
                result_schema = _response_result(operation, raw_operation, source)
                scopes = _operation_scopes(operation, raw_operation, source)
                operations.append(
                    OperationSpec(
                        operation=operation,
                        source=source,
                        payload_schema=payload_schema,
                        result_schema=result_schema,
                        scopes=scopes,
                    )
                )
    return tuple(sorted(operations, key=lambda item: item.operation))


def _direct_reference(schema: dict[str, object]) -> str | None:
    reference = schema.get("$ref")
    if type(reference) is str:
        return _reference_name(reference, location="schema.$ref")
    return None


def _collect_refs(
    schema: dict[str, object],
    source: SourceDocument,
    *,
    collected: set[str],
    canonical_schemas: dict[str, tuple[SourceDocument, str]],
    seen: frozenset[str] = frozenset(),
) -> None:
    reference = _direct_reference(schema)
    if reference is not None:
        if reference in collected:
            return
        component = source.schemas.get(reference)
        if component is None:
            raise GenerationError(f"unknown schema reference {reference!r}")
        component_schema = _schema(
            component,
            location=f"{source.label}.components.schemas.{reference}",
        )
        if reference in CANONICAL_TYPES:
            serialized = _canonical_json(_normalize_schema_contract(component_schema))
            if serialized != _sdk_canonical_schema_contract(reference):
                raise GenerationError(
                    f"canonical schema {reference} does not match the SDK-owned contract"
                )
            previous = canonical_schemas.get(reference)
            if previous is not None and previous[1] != serialized:
                raise GenerationError(
                    f"global canonical schema collision for {reference}: "
                    f"{previous[0].label} and {source.label}"
                )
            canonical_schemas.setdefault(reference, (source, serialized))
            if reference in seen:
                return
            _collect_refs(
                component_schema,
                source,
                collected=collected,
                canonical_schemas=canonical_schemas,
                seen=seen | {reference},
            )
            return
        collected.add(reference)
        _collect_refs(
            component_schema,
            source,
            collected=collected,
            canonical_schemas=canonical_schemas,
            seen=seen | {reference},
        )
        return
    for key in ("anyOf", "oneOf", "allOf"):
        branches = schema.get(key)
        if branches is not None:
            for branch in _sequence(branches, location=f"schema.{key}"):
                _collect_refs(
                    _schema(branch, location=f"schema.{key}[]"),
                    source,
                    collected=collected,
                    canonical_schemas=canonical_schemas,
                    seen=seen,
                )
    items = schema.get("items")
    if items is not None:
        _collect_refs(
            _schema(items, location="schema.items"),
            source,
            collected=collected,
            canonical_schemas=canonical_schemas,
            seen=seen,
        )
    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        _collect_refs(
            additional,
            source,
            collected=collected,
            canonical_schemas=canonical_schemas,
            seen=seen,
        )
    properties = schema.get("properties")
    if properties is not None:
        for child in _mapping(properties, location="schema.properties").values():
            _collect_refs(
                _schema(child, location="schema property"),
                source,
                collected=collected,
                canonical_schemas=canonical_schemas,
                seen=seen,
            )


def collect_types(operations: Sequence[OperationSpec]) -> tuple[TypeSpec, ...]:
    """Collect reachable schemas and reject global class/module collisions before writing."""
    names: dict[str, SourceDocument] = {}
    modules: dict[str, str] = {}
    canonical_schemas: dict[str, tuple[SourceDocument, str]] = {}
    result: list[TypeSpec] = []
    for operation in operations:
        reachable: set[str] = set()
        _collect_refs(
            operation.payload_schema,
            operation.source,
            collected=reachable,
            canonical_schemas=canonical_schemas,
        )
        _collect_refs(
            operation.result_schema,
            operation.source,
            collected=reachable,
            canonical_schemas=canonical_schemas,
        )
        for name in sorted(reachable):
            if PYTHON_NAME_PATTERN.fullmatch(name) is None or keyword.iskeyword(name):
                raise GenerationError(f"schema {name!r} is not a valid public Python type")
            previous = names.get(name)
            if previous is not None and previous is not operation.source:
                raise GenerationError(
                    f"global schema collision for {name}: {previous.label} and "
                    f"{operation.source.label}"
                )
            module = to_snake_case(name)
            previous_name = modules.get(module)
            if previous_name is not None and previous_name != name:
                raise GenerationError(
                    f"global schema module collision for {previous_name} and {name}"
                )
            if previous is None:
                names[name] = operation.source
                modules[module] = name
                component = operation.source.schemas[name]
                result.append(
                    TypeSpec(
                        name=name,
                        schema=_schema(component, location=f"components.schemas.{name}"),
                        source=operation.source,
                    )
                )
    return tuple(sorted(result, key=lambda item: item.name))
