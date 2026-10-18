"""Reachable schema graphs and compatibility with the SDK-owned canonical catalog."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from scripts import generate_methods as generator
from tests.generator_builders import document, object_schema, operation


def parsed(raw: dict[str, Any]) -> generator.SourceDocument:
    return generator.parse_document(raw, label="synthetic.json")


def reference(name: str) -> dict[str, str]:
    return {"$ref": "#/components/schemas/" + name}


def test_reachable_graph_contains_shared_array_union_and_allof_types(tmp_path: Path) -> None:
    raw = document(
        payload=object_schema(
            {
                "first": reference("TechnicalLeaf"),
                "second": reference("TechnicalLeaf"),
                "many": {"type": "array", "items": reference("TechnicalContainer")},
                "choice": {"anyOf": [reference("TechnicalLeaf"), {"type": "null"}]},
                "other": {"oneOf": [reference("TechnicalLeaf"), {"type": "integer"}]},
            }
        )
    )
    raw["components"]["schemas"] = {
        "TechnicalLeaf": object_schema({"value": {"type": "integer"}}, ["value"]),
        "TechnicalContainer": {
            "allOf": [
                object_schema({"leaf": reference("TechnicalLeaf")}),
                object_schema({"count": {"type": "integer"}}),
            ]
        },
        "Unused": {"type": "integer"},
    }
    specs = generator.collect_operations((parsed(raw),))
    types = generator.collect_types(specs)
    assert [item.name for item in types] == ["TechnicalContainer", "TechnicalLeaf"]
    output = tmp_path / "pypokerlost"
    assert "2 flat types" in generator.generate((parsed(raw),), output=output, check=False)
    assert not (output / "types/unused.py").exists()
    for path in output.rglob("*.py"):
        compile(path.read_text(), str(path), "exec")


def test_map_value_schemas_are_reachable_and_generated(tmp_path: Path) -> None:
    raw = document(
        payload=object_schema(
            {"records": {"type": "object", "additionalProperties": reference("TechnicalLeaf")}},
            ["records"],
        )
    )
    raw["components"]["schemas"] = {
        "TechnicalLeaf": object_schema({"value": {"type": "integer"}}, ["value"])
    }
    types = generator.collect_types(generator.collect_operations((parsed(raw),)))
    assert [item.name for item in types] == ["TechnicalLeaf"]
    output = tmp_path / "pypokerlost"
    generator.generate((parsed(raw),), output=output, check=False)
    assert (output / "types/technical_leaf.py").is_file()


@pytest.mark.parametrize("name", ["PokerlostToken", "PokerlostTokenKey", "JSONValue"])
def test_canonical_references_are_verified_and_never_rewritten(name: str, tmp_path: Path) -> None:
    schema = TypeAdapter(generator.CANONICAL_SCHEMA_TYPES[name]).json_schema(
        ref_template="#/components/schemas/{model}"
    )
    definitions = schema.pop("$defs", {})
    if schema == reference(name):
        schema = definitions.pop(name)
    raw = document(payload=object_schema({"canonical": reference(name)}))
    raw["components"]["schemas"] = {**definitions, name: schema}
    operations = generator.collect_operations((parsed(raw),))
    assert generator.collect_types(operations) == ()
    output = tmp_path / "pypokerlost"
    generator.generate((parsed(raw),), output=output, check=False)
    assert not (output / "types" / (generator.to_snake_case(name) + ".py")).exists()
    changed = deepcopy(raw)
    changed["components"]["schemas"][name]["unexpectedConstraint"] = True
    with pytest.raises(generator.GenerationError, match="does not match"):
        generator.collect_operations((parsed(changed),))


def test_entire_canonical_catalog_has_stable_normalized_schemas() -> None:
    for name in generator.CANONICAL_SCHEMA_TYPES:
        first = generator._sdk_canonical_schema_contract(name)
        assert first == generator._sdk_canonical_schema_contract(name)
        assert first.startswith("{")


@pytest.mark.parametrize("name", ["bad_name", "badName", "True"])
def test_reachable_type_names_must_be_valid_public_python_names(name: str) -> None:
    raw = document(payload=object_schema({"field": reference(name)}))
    raw["components"]["schemas"][name] = {"type": "integer"}
    with pytest.raises(generator.GenerationError, match="valid public Python type"):
        generator.collect_types(generator.collect_operations((parsed(raw),)))


def test_global_type_name_and_module_collisions_are_rejected() -> None:
    documents = []
    for name in ("technicalFirst", "technicalSecond"):
        raw = document(name, payload=object_schema({"field": reference("TechnicalLeaf")}))
        raw["components"]["schemas"]["TechnicalLeaf"] = {"type": "integer"}
        documents.append(parsed(raw))
    with pytest.raises(generator.GenerationError, match="global schema collision"):
        generator.collect_types(generator.collect_operations(documents))
    raw = document(
        payload=object_schema({"first": reference("ReadXML"), "second": reference("ReadXml")})
    )
    raw["components"]["schemas"] = {"ReadXML": {"type": "integer"}, "ReadXml": {"type": "integer"}}
    with pytest.raises(generator.GenerationError, match="module collision"):
        generator.collect_types(generator.collect_operations((parsed(raw),)))


@pytest.mark.parametrize("kind", ["missing", "external", "recursiveEnvelope", "invalidComponent"])
def test_invalid_references_fail_without_output(tmp_path: Path, kind: str) -> None:
    raw = document()
    media = operation(raw)["requestBody"]["content"]["application/json"]
    media["schema"] = reference("TechnicalEnvelope")
    if kind == "external":
        media["schema"] = {"$ref": "https://outside.invalid/schema"}
    elif kind == "recursiveEnvelope":
        raw["components"]["schemas"]["TechnicalEnvelope"] = reference("TechnicalEnvelope")
    elif kind == "invalidComponent":
        raw["components"]["schemas"]["TechnicalEnvelope"] = []
    output = tmp_path / "pypokerlost"
    with pytest.raises(generator.GenerationError):
        generator.generate((parsed(raw),), output=output, check=False)
    assert not output.exists()
