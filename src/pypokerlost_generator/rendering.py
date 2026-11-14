"""Pure deterministic rendering of validated flat SDK modules."""

from __future__ import annotations

import keyword
import math
from collections.abc import Iterable, Mapping

from pypokerlost_generator.models import (
    CANONICAL_ENUM_TYPES,
    CANONICAL_TYPES,
    GENERATED_HEADER,
    GENERATOR_VERSION,
    SDK_SCOPE_MEMBER_BY_VALUE,
    SECRET_FIELD_NAMES,
    SECRET_FIELD_SUFFIXES,
    GenerationError,
    OperationSpec,
    SourceDocument,
    TypeSpec,
    to_snake_case,
)
from pypokerlost_generator.schema import (
    _direct_reference,
    _object_properties,
    _resolve_schema,
    _schema,
    _sequence,
)


def _python_literal(value: object) -> str:
    if value is None or type(value) in {bool, int, float, str}:
        if type(value) is float and not math.isfinite(value):
            raise GenerationError("schema literals must be finite")
        return repr(value)
    raise GenerationError("only scalar JSON Schema literals are supported")


def _render_annotation(
    schema: dict[str, object],
    source: SourceDocument,
    *,
    imports: set[tuple[str, str]],
) -> str:
    reference = _direct_reference(schema)
    if reference is not None:
        if reference in CANONICAL_TYPES:
            module = (
                "pypokerlost.enums" if reference in CANONICAL_ENUM_TYPES else "pypokerlost.types"
            )
            imports.add((module, reference))
        else:
            imports.add((f"pypokerlost.types.{to_snake_case(reference)}", reference))
        return reference
    branches_value = schema.get("anyOf", schema.get("oneOf"))
    if branches_value is not None:
        expressions = {
            _render_annotation(
                _schema(branch, location="schema union branch"),
                source,
                imports=imports,
            )
            for branch in _sequence(branches_value, location="schema union")
        }
        return " | ".join(sorted(expressions, key=lambda item: (item == "None", item)))
    enum = schema.get("enum")
    if enum is not None:
        imports.add(("typing", "Literal"))
        values = ", ".join(
            _python_literal(value) for value in _sequence(enum, location="schema.enum")
        )
        return f"Literal[{values}]"
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        expressions = {
            _render_annotation({**schema, "type": item}, source, imports=imports)
            for item in raw_type
        }
        return " | ".join(sorted(expressions, key=lambda item: (item == "None", item)))
    if raw_type == "null":
        return "None"
    if raw_type == "boolean":
        return "bool"
    if raw_type == "integer":
        return "int"
    if raw_type == "number":
        return "float"
    if raw_type == "string":
        format_value = schema.get("format")
        if format_value == "uuid":
            imports.add(("uuid", "UUID"))
            return "UUID"
        if format_value == "date":
            imports.add(("datetime", "date"))
            return "date"
        if format_value == "date-time":
            imports.add(("datetime", "datetime"))
            return "datetime"
        if format_value == "time":
            imports.add(("datetime", "time"))
            return "time"
        if format_value == "password":
            return "str"
        if format_value is not None:
            raise GenerationError(f"unsupported string format {format_value!r}")
        return "str"
    if raw_type == "array":
        items = _schema(schema.get("items"), location="schema.items")
        return f"tuple[{_render_annotation(items, source, imports=imports)}, ...]"
    if raw_type == "object" and not schema.get("properties"):
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            value_type = _render_annotation(
                _schema(additional, location="schema.additionalProperties"),
                source,
                imports=imports,
            )
        else:
            imports.add(("pypokerlost.types", "JSONValue"))
            value_type = "JSONValue"
        return f"dict[str, {value_type}]"
    if "properties" in schema or raw_type == "object":
        raise GenerationError("inline typed object schemas must be named components")
    raise GenerationError("unsupported or untyped JSON Schema")


def _render_imports(imports: Iterable[tuple[str, str]]) -> str:
    grouped: dict[str, set[str]] = {}
    for module, name in imports:
        grouped.setdefault(module, set()).add(name)
    lines: list[str] = []
    previous_category: int | None = None
    for module in sorted(grouped, key=lambda item: (_import_category(item), item)):
        category = _import_category(module)
        if previous_category is not None and category != previous_category:
            lines.append("")
        names = sorted(grouped[module])
        if len(names) == 1:
            lines.append(f"from {module} import {names[0]}")
        else:
            lines.append(f"from {module} import (")
            lines.extend(f"    {name}," for name in names)
            lines.append(")")
        previous_category = category
    return "\n".join(lines)


def _import_category(module: str) -> int:
    if module.startswith("pypokerlost"):
        return 2
    if module == "pydantic" or module.startswith("pydantic."):
        return 1
    return 0


def _required_fields(
    schema: dict[str, object],
    source: SourceDocument,
    *,
    location: str,
) -> tuple[dict[str, object], frozenset[str]]:
    resolved = _resolve_schema(schema, source, location=location)
    return _object_properties(resolved, source, location=location)


def _render_field(
    name: str,
    raw_schema: object,
    *,
    required: bool,
    source: SourceDocument,
    imports: set[tuple[str, str]],
) -> str:
    if not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_"):
        raise GenerationError(f"wire field {name!r} is not a supported Python identifier")
    schema = _schema(raw_schema, location=f"field {name}")
    annotation = _render_annotation(schema, source, imports=imports)
    field_kwargs: list[str] = []
    if name in SECRET_FIELD_NAMES or name.endswith(SECRET_FIELD_SUFFIXES):
        field_kwargs.append("repr=False")
    if not required:
        if "None" not in annotation.split(" | "):
            annotation = f"{annotation} | None"
        field_kwargs.insert(0, "default=None")
    if field_kwargs:
        imports.add(("pydantic", "Field"))
        return f"{name}: {annotation} = Field({', '.join(field_kwargs)})"
    return f"{name}: {annotation}"


def _generated_preamble(source: SourceDocument) -> str:
    return (
        GENERATED_HEADER
        + f"# Generator version: {GENERATOR_VERSION}\n"
        + f"# OpenAPI version: {source.version}\n"
        + f"# OpenAPI SHA256: {source.source_sha256}\n"
        + "# Do not edit manually.\n"
    )


def render_type(spec: TypeSpec) -> str:
    """Render one component into one focused flat module."""
    resolved = _resolve_schema(spec.schema, spec.source, location=spec.name)
    properties = resolved.get("properties")
    if properties is None and resolved.get("type") != "object":
        imports: set[tuple[str, str]] = set()
        annotation = _render_annotation(resolved, spec.source, imports=imports)
        return (
            _generated_preamble(spec.source)
            + f'"""Generated Pokerlost type {spec.name}."""\n\n'
            + "from __future__ import annotations\n\n"
            + (_render_imports(imports) + "\n\n" if imports else "")
            + f"type {spec.name} = {annotation}\n"
        )
    fields, required = _required_fields(
        resolved,
        spec.source,
        location=spec.name,
    )
    imports = {("pypokerlost.types.base", "PokerlostType")}
    field_lines = [
        "    "
        + _render_field(
            name,
            field,
            required=name in required,
            source=spec.source,
            imports=imports,
        )
        for name, field in sorted(fields.items())
    ]
    if not field_lines:
        field_lines = ["    pass"]
    return (
        _generated_preamble(spec.source)
        + f'"""Generated Pokerlost type {spec.name}."""\n\n'
        + "from __future__ import annotations\n\n"
        + _render_imports(imports)
        + "\n\n\n"
        + f"class {spec.name}(PokerlostType):\n"
        + "\n".join(field_lines)
        + "\n"
    )


def render_method(
    spec: OperationSpec,
    scopes: tuple[str, ...] | None,
) -> str:
    """Render one flat method with explicit operation and scope metadata."""
    payload, required = _required_fields(
        spec.payload_schema,
        spec.source,
        location=f"{spec.operation}.payload",
    )
    imports: set[tuple[str, str]] = {
        ("pypokerlost.methods.base", "PokerlostMethod"),
        ("pypokerlost.types", "PokerlostOperation"),
        ("pypokerlost.enums", "PokerlostScopes"),
        ("typing", "ClassVar"),
    }
    result = _render_annotation(spec.result_schema, spec.source, imports=imports)
    field_lines = [
        "    "
        + _render_field(
            name,
            field,
            required=name in required,
            source=spec.source,
            imports=imports,
        )
        for name, field in sorted(payload.items())
    ]
    if scopes is not None:
        scope_lines = ["    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = ("]
        for scope in scopes:
            member = SDK_SCOPE_MEMBER_BY_VALUE.get(scope)
            if member is None:
                raise GenerationError(f"scope {scope!r} is absent from PokerlostScopes")
            scope_lines.append(f"        PokerlostScopes.{member},")
        scope_lines.append("    )")
    else:
        scope_lines = ["    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = None"]
    body = [
        f"class {spec.class_name}(PokerlostMethod[{result}]):",
        f'    operation = PokerlostOperation("{spec.operation}")',
        *scope_lines,
        f"    returning = {'type(None)' if result == 'None' else result}",
    ]
    if field_lines:
        body.extend(("", *field_lines))
    return (
        _generated_preamble(spec.source)
        + f'"""Generated Pokerlost method {spec.class_name}."""\n\n'
        + "from __future__ import annotations\n\n"
        + _render_imports(imports)
        + "\n\n\n"
        + "\n".join(body)
        + "\n"
    )


def _render_facade(
    *,
    title: str,
    modules: Mapping[str, tuple[str, ...]],
) -> str:
    imports = {(f".{module}", name) for module, names in modules.items() for name in names}
    exports = sorted(name for names in modules.values() for name in names)
    return (
        GENERATED_HEADER
        + f"# Generator version: {GENERATOR_VERSION}\n"
        + "# Do not edit manually.\n"
        + f'"""{title}."""\n\n'
        + "from __future__ import annotations\n\n"
        + _render_imports(imports)
        + "\n\n__all__ = (\n"
        + "".join(f'    "{name}",\n' for name in exports)
        + ")\n"
    )
