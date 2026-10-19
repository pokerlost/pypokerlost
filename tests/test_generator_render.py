"""Compile rendered modules and verify type, scope and secret-field contracts."""

from __future__ import annotations

import ast
from typing import Any

import pytest

from scripts import generate_methods as generator
from tests.generator_builders import SCOPE, document, object_schema


@pytest.fixture
def source() -> generator.SourceDocument:
    return generator.parse_document(document(), label="synthetic.json")


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"type": "null"}, "None"),
        ({"type": "boolean"}, "bool"),
        ({"type": "integer"}, "int"),
        ({"type": "number"}, "float"),
        ({"type": "string"}, "str"),
        ({"type": "string", "format": "uuid"}, "UUID"),
        ({"type": "string", "format": "date"}, "date"),
        ({"type": "string", "format": "date-time"}, "datetime"),
        ({"type": "string", "format": "time"}, "time"),
        ({"type": "string", "format": "password"}, "str"),
        ({"type": ["string", "null"]}, "str | None"),
        (
            {"anyOf": [{"type": "string"}, {"type": "null"}, {"type": "integer"}]},
            "int | str | None",
        ),
        ({"oneOf": [{"type": "integer"}, {"type": "integer"}]}, "int"),
        ({"type": "array", "items": {"type": "integer"}}, "tuple[int, ...]"),
        ({"type": "object", "additionalProperties": {"type": "integer"}}, "dict[str, int]"),
        ({"type": "object"}, "dict[str, JSONValue]"),
        ({"enum": ["one", 2, None, True]}, "Literal['one', 2, None, True]"),
        ({"$ref": "#/components/schemas/PokerlostAudience"}, "PokerlostAudience"),
        ({"$ref": "#/components/schemas/PokerlostScopes"}, "PokerlostScopes"),
        ({"$ref": "#/components/schemas/TechnicalRecord"}, "TechnicalRecord"),
    ],
)
def test_schema_annotations_are_valid_python(
    source: generator.SourceDocument, schema: dict[str, Any], expected: str
) -> None:
    imports: set[tuple[str, str]] = set()
    rendered = generator._render_annotation(schema, source, imports=imports)
    assert rendered == expected
    ast.parse(f"type TechnicalAlias = {rendered}")
    if "$ref" in schema:
        assert imports


@pytest.mark.parametrize(
    "schema",
    [
        {},
        {"type": "string", "format": "unsupported"},
        {"type": "object", "properties": {"field": {"type": "string"}}},
        {"type": "array"},
        {"enum": [[1]]},
        {"enum": [float("nan")]},
        {"$ref": "https://outside.invalid/schema"},
        {"$ref": "#/components/schemas/a/b"},
        {"$ref": "#/components/schemas/"},
        {"$ref": "#/components/schemas/a~1b"},
    ],
)
def test_unsupported_schemas_fail_instead_of_emitting_invalid_code(
    source: generator.SourceDocument, schema: dict[str, Any]
) -> None:
    with pytest.raises(generator.GenerationError):
        generator._render_annotation(schema, source, imports=set())


@pytest.mark.parametrize(
    ("name", "required", "expected"),
    [
        ("value", True, "value: str"),
        ("value", False, "value: str | None = Field(default=None)"),
        ("client_secret", True, "client_secret: str = Field(repr=False)"),
        (
            "service_private_key",
            False,
            "service_private_key: str | None = Field(default=None, repr=False)",
        ),
    ],
)
def test_field_requiredness_and_secret_repr_are_explicit(
    source: generator.SourceDocument, name: str, required: bool, expected: str
) -> None:
    imports: set[tuple[str, str]] = set()
    assert (
        generator._render_field(
            name, {"type": "string"}, required=required, source=source, imports=imports
        )
        == expected
    )
    assert (("pydantic", "Field") in imports) == (not required or name != "value")
    nullable = generator._render_field(
        name, {"type": ["string", "null"]}, required=False, source=source, imports=imports
    )
    assert nullable.count("None") == 2


@pytest.mark.parametrize("name", ["", "invalid-name", "class", "_private", "bad\nname"])
def test_wire_fields_cannot_inject_or_hide_python_names(
    source: generator.SourceDocument, name: str
) -> None:
    with pytest.raises(generator.GenerationError, match="identifier"):
        generator._render_field(
            name, {"type": "integer"}, required=True, source=source, imports=set()
        )


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "integer"},
        {"type": "string", "format": "uuid"},
        object_schema(),
        object_schema({"value": {"type": "integer"}}, ["value"]),
    ],
)
def test_rendered_component_aliases_and_objects_compile(
    source: generator.SourceDocument, schema: dict[str, Any]
) -> None:
    spec = generator.TypeSpec("TechnicalRecord", schema, source)
    rendered = generator.render_type(spec)
    assert spec.module_name == "technical_record"
    assert rendered.startswith(generator.GENERATED_HEADER)
    assert source.source_sha256 in rendered
    compile(rendered, "technical_record.py", "exec")


@pytest.mark.parametrize("protected", [False, True])
def test_rendered_methods_have_explicit_canonical_scopes(protected: bool) -> None:
    raw = document(protected=protected)
    source = generator.parse_document(raw, label="synthetic.json")
    spec = generator.collect_operations((source,))[0]
    rendered = generator.render_method(spec, spec.scopes)
    compile(rendered, "technical_probe.py", "exec")
    metadata = generator._method_metadata_from_source(
        rendered, "TechnicalProbe", label="rendered", scope_members=generator.SDK_SCOPE_MEMBERS
    )
    assert str(metadata.operation) == "technicalProbe"
    assert metadata.scopes == ((SCOPE,) if protected else None)
    assert metadata.result_annotation == "int"
    assert metadata.returning == "int"
    assert metadata.fields == {}


def test_none_return_and_unknown_scope_are_explicit(source: generator.SourceDocument) -> None:
    spec = generator.OperationSpec(
        generator.PokerlostOperation("technicalProbe"),
        source,
        object_schema(),
        {"type": "null"},
        None,
    )
    rendered = generator.render_method(spec, None)
    assert "returning = type(None)" in rendered
    compile(rendered, "technical_probe.py", "exec")
    with pytest.raises(generator.GenerationError, match="absent from PokerlostScopes"):
        generator.render_method(spec, ("future.operation",))


def test_schema_normalization_ignores_documentation_but_preserves_wire_constraints() -> None:
    schema = {
        "title": "Documentation",
        "description": "text",
        "minimum": 1.0,
        "enum": [2, 1],
        "required": ["b", "a"],
        "allOf": [{"type": "string"}, {"type": "null"}],
    }
    normalized = generator._normalize_schema_contract(schema)
    assert normalized == {
        "minimum": 1,
        "enum": [1, 2],
        "required": ["a", "b"],
        "allOf": [{"type": "null"}, {"type": "string"}],
    }
    assert generator._normalize_schema_contract({"minimum": 1.5}) == {"minimum": 1.5}
    with pytest.raises(generator.GenerationError):
        generator._normalize_schema_contract({1: "invalid key"})
    with pytest.raises(generator.GenerationError):
        generator._normalize_schema_contract({"enum": {"not": "array"}})


def test_imports_are_grouped_deduplicated_and_stable() -> None:
    imports = [
        ("typing", "Literal"),
        ("typing", "ClassVar"),
        ("pydantic", "Field"),
        ("pypokerlost.types", "PokerlostToken"),
        ("typing", "Literal"),
    ]
    value = generator._render_imports(imports)
    assert value.count("Literal") == 1
    assert value.index("typing") < value.index("pydantic") < value.index("pypokerlost")
    compile(value, "imports.py", "exec")
