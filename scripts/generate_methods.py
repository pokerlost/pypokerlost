#!/usr/bin/env python3
"""Compatible generator facade, CLI and filesystem orchestration.

Pure models, schema validation/resolution and rendering live in the optional
``pypokerlost_generator`` package. Existing imports and direct script usage remain
available here; this module owns repository-relative manifest paths and writes.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Never

import httpx
import typer
from pydantic import TypeAdapter

from pypokerlost import enums as pokerlost_enums
from pypokerlost import types as pokerlost_types
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.client.pokerlost_api_server import SERVICE_ID_HEADER
from pypokerlost.types import PokerlostOperation
from pypokerlost_generator.models import CANONICAL_ENUM_TYPES as CANONICAL_ENUM_TYPES
from pypokerlost_generator.models import CANONICAL_FUNCTION_EXPORTS as CANONICAL_FUNCTION_EXPORTS
from pypokerlost_generator.models import CANONICAL_SCHEMA_TYPES as CANONICAL_SCHEMA_TYPES
from pypokerlost_generator.models import CANONICAL_TYPES as CANONICAL_TYPES
from pypokerlost_generator.models import CONTRACT_VERSION as CONTRACT_VERSION
from pypokerlost_generator.models import ENVELOPE_FIELDS as ENVELOPE_FIELDS
from pypokerlost_generator.models import GENERATED_HEADER as GENERATED_HEADER
from pypokerlost_generator.models import GENERATOR_VERSION as GENERATOR_VERSION
from pypokerlost_generator.models import (
    INFRASTRUCTURE_GET_OPERATIONS as INFRASTRUCTURE_GET_OPERATIONS,
)
from pypokerlost_generator.models import MANIFEST_VERSION as MANIFEST_VERSION
from pypokerlost_generator.models import OPERATION_PATTERN as OPERATION_PATTERN
from pypokerlost_generator.models import POKERLOST_SECURITY_SCHEME as POKERLOST_SECURITY_SCHEME
from pypokerlost_generator.models import PYTHON_NAME_PATTERN as PYTHON_NAME_PATTERN
from pypokerlost_generator.models import SCOPE_PATTERN as SCOPE_PATTERN
from pypokerlost_generator.models import SDK_SCOPE_MEMBER_BY_VALUE as SDK_SCOPE_MEMBER_BY_VALUE
from pypokerlost_generator.models import SDK_SCOPE_MEMBERS as SDK_SCOPE_MEMBERS
from pypokerlost_generator.models import SDK_SCOPE_VALUES as SDK_SCOPE_VALUES
from pypokerlost_generator.models import SECRET_FIELD_NAMES as SECRET_FIELD_NAMES
from pypokerlost_generator.models import SECRET_FIELD_SUFFIXES as SECRET_FIELD_SUFFIXES
from pypokerlost_generator.models import SEMVER_PATTERN as SEMVER_PATTERN
from pypokerlost_generator.models import GenerationError as GenerationError
from pypokerlost_generator.models import HandwrittenMethodMetadata as HandwrittenMethodMetadata
from pypokerlost_generator.models import NonEmptyString as NonEmptyString
from pypokerlost_generator.models import OperationSpec as OperationSpec
from pypokerlost_generator.models import RenderedFile as RenderedFile
from pypokerlost_generator.models import SourceDocument as SourceDocument
from pypokerlost_generator.models import TypeSpec as TypeSpec
from pypokerlost_generator.models import to_snake_case as to_snake_case
from pypokerlost_generator.rendering import _generated_preamble as _generated_preamble
from pypokerlost_generator.rendering import _import_category as _import_category
from pypokerlost_generator.rendering import _python_literal as _python_literal
from pypokerlost_generator.rendering import _render_annotation as _render_annotation
from pypokerlost_generator.rendering import _render_facade as _render_facade
from pypokerlost_generator.rendering import _render_field as _render_field
from pypokerlost_generator.rendering import _render_imports as _render_imports
from pypokerlost_generator.rendering import _required_fields as _required_fields
from pypokerlost_generator.rendering import render_method as render_method
from pypokerlost_generator.rendering import render_type as render_type
from pypokerlost_generator.schema import (
    _ORDER_INSENSITIVE_SCHEMA_ARRAYS as _ORDER_INSENSITIVE_SCHEMA_ARRAYS,
)
from pypokerlost_generator.schema import _SCHEMA_ANNOTATION_KEYS as _SCHEMA_ANNOTATION_KEYS
from pypokerlost_generator.schema import _canonical_json as _canonical_json
from pypokerlost_generator.schema import _collect_refs as _collect_refs
from pypokerlost_generator.schema import _direct_reference as _direct_reference
from pypokerlost_generator.schema import _json_object as _json_object
from pypokerlost_generator.schema import _mapping as _mapping
from pypokerlost_generator.schema import _normalize_schema_contract as _normalize_schema_contract
from pypokerlost_generator.schema import _oauth2_catalog as _oauth2_catalog
from pypokerlost_generator.schema import _object_properties as _object_properties
from pypokerlost_generator.schema import _operation_scopes as _operation_scopes
from pypokerlost_generator.schema import _optional_mapping as _optional_mapping
from pypokerlost_generator.schema import _reference_name as _reference_name
from pypokerlost_generator.schema import _reject_extensions as _reject_extensions
from pypokerlost_generator.schema import _request_envelope as _request_envelope
from pypokerlost_generator.schema import _resolve_schema as _resolve_schema
from pypokerlost_generator.schema import _response_result as _response_result
from pypokerlost_generator.schema import _schema as _schema
from pypokerlost_generator.schema import _schema_kinds as _schema_kinds
from pypokerlost_generator.schema import _scope_value as _scope_value
from pypokerlost_generator.schema import (
    _sdk_canonical_schema_contract as _sdk_canonical_schema_contract,
)
from pypokerlost_generator.schema import _sequence as _sequence
from pypokerlost_generator.schema import _string as _string
from pypokerlost_generator.schema import _strip_null as _strip_null
from pypokerlost_generator.schema import _track_canonical_references as _track_canonical_references
from pypokerlost_generator.schema import collect_operations as collect_operations
from pypokerlost_generator.schema import collect_types as collect_types
from pypokerlost_generator.schema import parse_document as parse_document

DEFAULT_OUTPUT = Path("src/pypokerlost")


DEFAULT_CONTRACT_OUTPUT = Path("docs/api/sdk_contract.json")


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


MANIFEST_ROOT = REPOSITORY_ROOT / "scripts" / ".generated_methods"


def _method_metadata(
    path: Path,
    class_name: str,
    *,
    scope_members: Mapping[str, str],
) -> HandwrittenMethodMetadata:
    """Read direct class metadata from a hand-written method without importing it."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"cannot inspect hand-written method {path}") from error
    return _method_metadata_from_source(
        source,
        class_name,
        label=str(path),
        scope_members=scope_members,
    )


def _method_metadata_from_source(
    source: str,
    class_name: str,
    *,
    label: str,
    scope_members: Mapping[str, str],
) -> HandwrittenMethodMetadata:
    try:
        tree = ast.parse(source, filename=label)
    except SyntaxError as error:
        raise GenerationError(f"cannot inspect hand-written method {label}") from error
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        if len(node.bases) != 1 or not isinstance(node.bases[0], ast.Subscript):
            raise GenerationError(f"{label} must inherit directly from PokerlostMethod[ResultT]")
        base = node.bases[0]
        if not isinstance(base.value, ast.Name) or base.value.id != "PokerlostMethod":
            raise GenerationError(f"{label} must inherit directly from PokerlostMethod[ResultT]")
        result_annotation = _annotation_contract(base.slice)
        operation: PokerlostOperation | None = None
        scopes: tuple[str, ...] | None = None
        scopes_found = False
        fields: dict[str, tuple[str, bool]] = {}
        returning: str | None = None
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                if statement.target.id == "__scopes__":
                    if scopes_found:
                        raise GenerationError(f"{label} must declare __scopes__ exactly once")
                    scopes_found = True
                    annotation = ast.unparse(statement.annotation).replace(" ", "")
                    if annotation != "ClassVar[tuple[PokerlostScopes,...]|None]":
                        raise GenerationError(
                            f"{label} __scopes__ must use the canonical ClassVar annotation"
                        )
                    if statement.value is None:
                        raise GenerationError(f"{label} __scopes__ must have an explicit value")
                    if isinstance(statement.value, ast.Constant) and statement.value.value is None:
                        scopes = None
                        continue
                    if not isinstance(statement.value, ast.Tuple):
                        raise GenerationError(f"{label} __scopes__ must be None or a literal tuple")
                    if not statement.value.elts:
                        raise GenerationError(f"{label} __scopes__ must not be an empty tuple")
                    parsed_scopes: list[str] = []
                    for item in statement.value.elts:
                        if (
                            not isinstance(item, ast.Attribute)
                            or not isinstance(item.value, ast.Name)
                            or item.value.id != "PokerlostScopes"
                        ):
                            raise GenerationError(
                                f"{label} __scopes__ must contain PokerlostScopes members"
                            )
                        scope = scope_members.get(item.attr)
                        if scope is None:
                            raise GenerationError(
                                f"{label} references unknown PokerlostScopes member {item.attr}"
                            )
                        parsed_scopes.append(scope)
                    if len(frozenset(parsed_scopes)) != len(parsed_scopes):
                        raise GenerationError(f"{label} __scopes__ contains duplicate members")
                    if parsed_scopes != sorted(parsed_scopes):
                        raise GenerationError(
                            f"{label} __scopes__ must use canonical scope ordering"
                        )
                    scopes = tuple(parsed_scopes)
                    continue
                fields[statement.target.id] = (
                    _annotation_contract(statement.annotation),
                    _field_is_required(statement.value),
                )
                continue
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if target.id == "operation":
                operation = PokerlostOperation(_call_string(statement.value, "PokerlostOperation"))
            elif target.id == "returning":
                if (
                    isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name)
                    and statement.value.func.id == "type"
                    and len(statement.value.args) == 1
                    and isinstance(statement.value.args[0], ast.Constant)
                    and statement.value.args[0].value is None
                ):
                    returning = "None"
                else:
                    returning = _annotation_contract(statement.value)
        if operation is None or not scopes_found or returning is None:
            raise GenerationError(
                f"{label} must declare operation, __scopes__, and returning directly"
            )
        return HandwrittenMethodMetadata(
            operation=operation,
            scopes=scopes,
            result_annotation=result_annotation,
            returning=returning,
            fields=fields,
        )
    raise GenerationError(f"{label} does not define {class_name}")


_ANNOTATION_SCALAR_ALIASES = {
    "PokerlostAudience": "str",
}


def _annotation_contract(node: ast.expr) -> str:
    """Normalize annotations enough to compare handwritten and rendered wire shapes."""
    if isinstance(node, ast.Subscript):
        if isinstance(node.value, ast.Name) and node.value.id == "Annotated":
            if not isinstance(node.slice, ast.Tuple) or not node.slice.elts:
                raise GenerationError("Annotated method field must contain its value type")
            return _annotation_contract(node.slice.elts[0])
        container = _annotation_contract(node.value)
        if isinstance(node.slice, ast.Tuple):
            arguments = ",".join(_annotation_contract(item) for item in node.slice.elts)
        else:
            arguments = _annotation_contract(node.slice)
        return f"{container}[{arguments}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        members = sorted({_annotation_contract(node.left), _annotation_contract(node.right)})
        return "|".join(members)
    if isinstance(node, ast.Name):
        return _ANNOTATION_SCALAR_ALIASES.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return ast.unparse(node).replace(" ", "")
    if isinstance(node, ast.Constant) and node.value is Ellipsis:
        return "..."
    return ast.unparse(node).replace(" ", "")


def _field_is_required(value: ast.expr | None) -> bool:
    if value is None:
        return True
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
        return False
    if value.func.id != "Field":
        return False
    if value.args:
        return isinstance(value.args[0], ast.Constant) and value.args[0].value is Ellipsis
    for keyword_argument in value.keywords:
        if keyword_argument.arg == "default":
            return (
                isinstance(keyword_argument.value, ast.Constant)
                and keyword_argument.value.value is Ellipsis
            )
        if keyword_argument.arg == "default_factory":
            return False
    return True


def _call_string(node: ast.expr, function_name: str) -> str:
    if (
        not isinstance(node, ast.Call)
        or not isinstance(node.func, ast.Name)
        or node.func.id != function_name
        or len(node.args) != 1
        or node.keywords
        or not isinstance(node.args[0], ast.Constant)
        or type(node.args[0].value) is not str
    ):
        raise GenerationError(f"{function_name} metadata must contain one string literal")
    return node.args[0].value


def _defined_public_types(path: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as error:
        raise GenerationError(f"cannot inspect public type module {path}") from error
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            names.append(node.name)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            if not node.name.id.startswith("_"):
                names.append(node.name.id)
        elif (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in CANONICAL_FUNCTION_EXPORTS
        ):
            names.append(node.name)
    return tuple(names)


def _defined_methods(path: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as error:
        raise GenerationError(f"cannot inspect method module {path}") from error
    result: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name == "PokerlostMethod" or any(
            isinstance(base, ast.Subscript)
            and isinstance(base.value, ast.Name)
            and base.value.id == "PokerlostMethod"
            for base in node.bases
        ):
            result.append(node.name)
    return tuple(result)


def _facade_modules(directory: Path, *, methods: bool) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for path in sorted(directory.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise GenerationError(f"cannot inspect facade module {path}") from error
        if content.startswith(GENERATED_HEADER):
            continue
        names = _defined_methods(path) if methods else _defined_public_types(path)
        if names:
            result[path.stem] = names
    return result


def _validate_handwritten_methods(
    directory: Path,
    *,
    scope_members: Mapping[str, str],
) -> None:
    """Validate every concrete handwritten method, including future-facing stubs."""
    seen_operations: dict[PokerlostOperation, Path] = {}
    seen_classes: dict[str, Path] = {}
    seen_modules: dict[str, PokerlostOperation] = {}
    for path in sorted(directory.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise GenerationError(f"cannot inspect hand-written method module {path}") from error
        if content.startswith(GENERATED_HEADER):
            continue
        for class_name in _defined_methods(path):
            if class_name == "PokerlostMethod":
                continue
            metadata = _method_metadata(
                path,
                class_name,
                scope_members=scope_members,
            )
            expected_class = metadata.operation[0].upper() + metadata.operation[1:]
            if class_name != expected_class:
                raise GenerationError(
                    f"{path} class name must match operation {metadata.operation}: {expected_class}"
                )
            expected_module = to_snake_case(metadata.operation)
            if path.stem != expected_module:
                raise GenerationError(
                    f"{path} module name must match operation {metadata.operation}: "
                    f"{expected_module}.py"
                )
            previous_operation = seen_operations.get(metadata.operation)
            if previous_operation is not None:
                raise GenerationError(
                    f"hand-written operation collision for {metadata.operation}: "
                    f"{previous_operation} and {path}"
                )
            previous_class = seen_classes.get(class_name)
            if previous_class is not None:
                raise GenerationError(
                    f"hand-written method class collision for {class_name}: "
                    f"{previous_class} and {path}"
                )
            previous_module = seen_modules.get(expected_module)
            if previous_module is not None:
                raise GenerationError(
                    f"hand-written method module collision for {previous_module} and "
                    f"{metadata.operation}: {path}"
                )
            seen_operations[metadata.operation] = path
            seen_classes[class_name] = path
            seen_modules[expected_module] = metadata.operation


def _manifest_path(output: Path) -> Path:
    if output.resolve() == (REPOSITORY_ROOT / "src/pypokerlost").resolve():
        return MANIFEST_ROOT / "flat.json"
    return output.parent / ".pypokerlost-generated" / "flat.json"


def _manifest_content(
    documents: Sequence[SourceDocument],
    owned_files: Iterable[Path],
) -> str:
    value = {
        "manifest_version": MANIFEST_VERSION,
        "generator_version": GENERATOR_VERSION,
        "sources": [
            {
                "title": document.title,
                "openapi_version": document.version,
                "source_sha256": document.source_sha256,
            }
            for document in sorted(
                documents,
                key=lambda item: (item.title, item.source_sha256),
            )
        ],
        "files": sorted(path.as_posix() for path in owned_files),
    }
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _previous_owned_files(path: Path) -> tuple[Path, ...]:
    if not path.exists():
        return ()
    try:
        raw = _json_object(path.read_text(encoding="utf-8"), location=str(path))
        files = _sequence(raw.get("files"), location=f"{path}.files")
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"failed to read generation manifest {path}") from error
    result: list[Path] = []
    for value in files:
        rendered = _string(value, location=f"{path}.files[]")
        candidate = Path(rendered)
        if candidate.is_absolute() or ".." in candidate.parts or candidate.suffix != ".py":
            raise GenerationError(f"generation manifest contains unsafe path {rendered!r}")
        result.append(candidate)
    return tuple(result)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    temporary.replace(path)


def render_protocol_contract() -> str:
    """Export shared vocabulary and schemas without deriving service capabilities."""
    value = {
        "contract_version": CONTRACT_VERSION,
        "routing_header": SERVICE_ID_HEADER,
        "service_ids": {member.name: member.value for member in pokerlost_enums.ServiceId},
        "common_error_codes": {
            member.name: member.value for member in pokerlost_enums.PokerlostErrorCode
        },
        "scopes": {member.name: member.value for member in pokerlost_enums.PokerlostScopes},
        "audience": {
            "open": True,
            "service_mapping": {
                service.name: str(pokerlost_types.PokerlostAudience.for_service(service))
                for service in pokerlost_enums.ServiceId
            },
        },
        "schemas": {
            "ServiceId": TypeAdapter(pokerlost_enums.ServiceId).json_schema(),
            "PokerlostErrorCode": TypeAdapter(pokerlost_enums.PokerlostErrorCode).json_schema(),
            "PokerlostRequest": TypeAdapter(pokerlost_types.PokerlostRequest[object]).json_schema(),
            "PokerlostResponse": TypeAdapter(
                pokerlost_types.PokerlostResponse[object]
            ).json_schema(),
        },
    }
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def export_protocol_contract(*, output: Path, check: bool) -> str:
    """Write or check the deterministic consumer artifact and its digest sidecar."""
    content = render_protocol_contract()
    digest_path = output.with_suffix(output.suffix + ".sha256")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    expected = {output: content, digest_path: f"{digest}  {output.name}\n"}
    differences: list[str] = []
    for path, rendered in expected.items():
        try:
            current = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = None
        except (OSError, UnicodeError) as error:
            raise GenerationError(f"failed to read protocol contract {path}") from error
        if current != rendered:
            differences.append(path.name)
    if check:
        if differences:
            raise GenerationError("protocol contract is out of date: " + ", ".join(differences))
        return "protocol contract and digest are up to date"
    try:
        for path, rendered in expected.items():
            _atomic_write(path, rendered)
    except OSError as error:
        raise GenerationError("failed to write protocol contract") from error
    return "exported protocol contract and digest"


def generate(
    documents: Sequence[SourceDocument],
    *,
    output: Path,
    check: bool,
) -> str:
    """Preflight globally, then check or write the complete generator-owned state."""
    operations = collect_operations(documents)
    scope_members = SDK_SCOPE_MEMBERS
    types = collect_types(operations)
    output = output.resolve()
    methods_directory = output / "methods"
    types_directory = output / "types"
    _validate_handwritten_methods(
        methods_directory,
        scope_members=scope_members,
    )
    rendered: list[RenderedFile] = []
    generated_method_names: dict[str, tuple[str, ...]] = {}
    generated_type_names: dict[str, tuple[str, ...]] = {}

    for type_spec in types:
        relative = Path("types") / f"{type_spec.module_name}.py"
        target = output / relative
        if target.exists() and not target.read_text(encoding="utf-8").startswith(GENERATED_HEADER):
            raise GenerationError(
                f"hand-written type {target} collides with generator-owned OpenAPI schema "
                f"{type_spec.name}"
            )
        rendered.append(RenderedFile(relative, render_type(type_spec)))
        generated_type_names[type_spec.module_name] = (type_spec.name,)

    for operation in operations:
        relative = Path("methods") / f"{operation.module_name}.py"
        target = output / relative
        if target.exists() and not target.read_text(encoding="utf-8").startswith(GENERATED_HEADER):
            declared = _method_metadata(
                target,
                operation.class_name,
                scope_members=scope_members,
            )
            expected = _method_metadata_from_source(
                render_method(operation, operation.scopes),
                operation.class_name,
                label=f"rendered {operation.class_name}",
                scope_members=scope_members,
            )
            if declared.operation != expected.operation:
                raise GenerationError(f"{target} operation metadata does not match OpenAPI")
            if declared.fields != expected.fields:
                raise GenerationError(
                    f"{target} payload field types or requiredness do not match OpenAPI"
                )
            if declared.result_annotation != expected.result_annotation:
                raise GenerationError(f"{target} generic result type does not match OpenAPI")
            if declared.returning != expected.returning:
                raise GenerationError(f"{target} result metadata does not match OpenAPI")
            if declared.scopes != expected.scopes:
                raise GenerationError(
                    f"{target} __scopes__ metadata does not match OpenAPI security"
                )
            continue
        rendered.append(RenderedFile(relative, render_method(operation, operation.scopes)))
        generated_method_names[operation.module_name] = (operation.class_name,)

    method_modules = _facade_modules(methods_directory, methods=True)
    method_modules.update(generated_method_names)
    type_modules = _facade_modules(types_directory, methods=False)
    type_modules.update(generated_type_names)
    rendered.extend(
        (
            RenderedFile(
                Path("methods/__init__.py"),
                _render_facade(
                    title="Flat public Pokerlost method facade",
                    modules=method_modules,
                ),
            ),
            RenderedFile(
                Path("types/__init__.py"),
                _render_facade(
                    title="Flat public Pokerlost type facade",
                    modules=type_modules,
                ),
            ),
        )
    )
    rendered.sort(key=lambda item: item.path.as_posix())
    manifest_path = _manifest_path(output)
    owned_files = tuple(item.path for item in rendered)
    expected_manifest = _manifest_content(documents, owned_files)
    previous_files = _previous_owned_files(manifest_path)
    current_files = frozenset(owned_files)
    differences: list[str] = []
    for item in rendered:
        target = output / item.path
        try:
            current = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = None
        except (OSError, UnicodeError) as error:
            raise GenerationError(f"failed to read generated target {target}") from error
        if current != item.content:
            differences.append(item.path.as_posix())
    stale = tuple(path for path in previous_files if path not in current_files)
    differences.extend(f"stale:{path.as_posix()}" for path in stale)
    try:
        current_manifest = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        current_manifest = None
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"failed to read generation manifest {manifest_path}") from error
    if current_manifest != expected_manifest:
        differences.append("manifest")
    if check:
        if differences:
            raise GenerationError(
                "generated SDK sources are out of date: " + ", ".join(differences)
            )
        return f"{len(operations)} operations and {len(types)} types are up to date"

    for item in rendered:
        target = output / item.path
        if target.exists() and item.path.name != "__init__.py":
            current = target.read_text(encoding="utf-8")
            if not current.startswith(GENERATED_HEADER):
                raise GenerationError(f"refusing to overwrite non-generator file {target}")
    for relative in stale:
        target = output / relative
        if relative.name == "__init__.py" or not target.exists():
            continue
        current = target.read_text(encoding="utf-8")
        if not current.startswith(GENERATED_HEADER):
            raise GenerationError(f"refusing to remove non-generator file {target}")

    for item in rendered:
        target = output / item.path
        _atomic_write(target, item.content)
    for relative in stale:
        target = output / relative
        if relative.name == "__init__.py" or not target.exists():
            continue
        target.unlink()
    _atomic_write(manifest_path, expected_manifest)
    return f"generated {len(operations)} operations and {len(types)} flat types"


def _read_source(path: Path) -> SourceDocument:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"failed to read OpenAPI file {path}") from error
    return parse_document(_json_object(text, location=str(path)), label=str(path))


async def _fetch_source(base_url: str, timeout: float) -> SourceDocument:
    if (
        type(timeout) is bool
        or not isinstance(timeout, int | float)
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise GenerationError("service timeout must be finite and positive")
    try:
        server = PokerlostAPIServer(base_url)
    except (TypeError, ValueError) as error:
        raise GenerationError(
            "service URL must be a root HTTPS URL or loopback HTTP URL"
        ) from error
    try:
        async with httpx.AsyncClient(timeout=float(timeout), trust_env=False) as client:
            response = await client.get(server.operation_url(PokerlostOperation("getOpenApi")))
            decoded: object = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise GenerationError("OpenAPI publication request failed") from error
    if not 200 <= response.status_code < 300:
        raise GenerationError("service refused OpenAPI publication")
    document = _mapping(decoded, location="OpenAPI publication response")
    return parse_document(document, label=base_url)


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    rich_markup_mode="markdown",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(GENERATOR_VERSION)
        raise typer.Exit()


@app.callback()
def cli(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Show the generator version and exit.",
        ),
    ] = False,
) -> None:
    """Generate flat SDK sources from the private Pokerlost JSON protocol."""


@app.command("contract", rich_help_panel="Contract sources")
def generate_protocol_contract(
    output: Annotated[
        Path, typer.Option("--output", "-o", dir_okay=False)
    ] = DEFAULT_CONTRACT_OUTPUT,
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    """Export the shared SDK protocol vocabulary and schemas for static consumers."""
    try:
        message = export_protocol_contract(output=output, check=check)
    except GenerationError as error:
        _fail(str(error))
    else:
        typer.secho(message, fg=typer.colors.GREEN)


@app.command("file", rich_help_panel="Contract sources")
def generate_from_files(
    sources: Annotated[
        list[Path],
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="One or more OpenAPI 3.1 JSON documents validated together.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", file_okay=False, dir_okay=True),
    ] = DEFAULT_OUTPUT,
    check: Annotated[bool, typer.Option("--check")] = False,
) -> None:
    """Preflight every local contract, then check or write one global flat output."""
    _execute_file(sources, output=output, check=check)


@app.command("service", rich_help_panel="Contract sources")
def generate_from_service(
    source: Annotated[str, typer.Argument(help="Root Pokerlost service URL.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", file_okay=False, dir_okay=True),
    ] = DEFAULT_OUTPUT,
    check: Annotated[bool, typer.Option("--check")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=0.001)] = 10.0,
) -> None:
    """Fetch the public getOpenApi body and generate from that single source."""
    try:
        document = asyncio.run(_fetch_source(source, timeout))
        message = generate(
            (document,),
            output=output,
            check=check,
        )
    except GenerationError as error:
        _fail(str(error))
    else:
        typer.secho(message, fg=typer.colors.GREEN)


def _execute_file(
    sources: Sequence[Path],
    *,
    output: Path,
    check: bool,
) -> None:
    if not sources:
        _fail("at least one OpenAPI source is required")
    try:
        documents = tuple(_read_source(path) for path in sources)
        message = generate(
            documents,
            output=output,
            check=check,
        )
    except GenerationError as error:
        _fail(str(error))
    else:
        typer.secho(message, fg=typer.colors.GREEN)


def _fail(message: str) -> Never:
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
