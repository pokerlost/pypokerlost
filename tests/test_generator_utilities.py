"""Schema union semantics and defensive input validation through real parsers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts import generate_methods as generator
from tests.generator_builders import document


@pytest.mark.parametrize(
    ("schema", "kinds"),
    [
        ({"type": ["integer", "null"]}, {"integer", "null"}),
        ({"$ref": "#/components/schemas/T"}, {"reference"}),
        ({"properties": {}}, {"object"}),
        ({}, set()),
        ({"anyOf": [{"type": "integer"}, {"type": "null"}]}, {"integer", "null"}),
    ],
)
def test_schema_kinds_are_structural(schema: dict[str, Any], kinds: set[str]) -> None:
    assert generator._schema_kinds(schema) == kinds


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "integer"},
        {"type": ["integer", "null"]},
        {"type": ["integer", "string", "null"]},
        {"type": ["integer", "string"]},
        {"anyOf": [{"type": "null"}, {"type": "integer"}, {"type": "string"}]},
        {"oneOf": [{"type": "null"}, {"type": "string"}]},
    ],
)
def test_success_result_strips_outer_envelope_null_consistently(schema: dict[str, Any]) -> None:
    original = deepcopy(schema)
    expected = generator._schema_kinds(schema) - {"null"}
    assert generator._schema_kinds(generator._strip_null(schema)) == expected
    assert schema == original


@pytest.mark.parametrize(
    "schema", [{"type": "null"}, {"anyOf": [{"type": "null"}]}, {"type": ["null"]}]
)
def test_null_only_result_remains_none(schema: dict[str, Any]) -> None:
    assert generator._schema_kinds(generator._strip_null(schema)) == {"null"}


@pytest.mark.parametrize(
    "value",
    [
        {"invalid": object()},
        {"invalid": {1, 2}},
        {"invalid": float("nan")},
        {"invalid": float("inf")},
    ],
)
def test_non_json_contract_values_fail_with_safe_errors(value: object) -> None:
    with pytest.raises(generator.GenerationError, match="non-JSON value"):
        generator._canonical_json(value)


def test_mapping_keys_cannot_be_coerced() -> None:
    with pytest.raises(generator.GenerationError, match="string keys"):
        generator._mapping({1: "synthetic-private-input"}, location="fixture")


def test_unknown_envelope_reference_is_rejected() -> None:
    source = generator.parse_document(document(), label="fixture")
    with pytest.raises(generator.GenerationError, match="unknown schema"):
        generator._resolve_schema(
            {"$ref": "#/components/schemas/Missing"}, source, location="fixture"
        )


def test_independent_type_collection_also_validates_references() -> None:
    source = generator.parse_document(document(), label="fixture")
    operation = generator.OperationSpec(
        generator.PokerlostOperation("technicalProbe"),
        source,
        {"$ref": "#/components/schemas/Missing"},
        {"type": "null"},
        None,
    )
    with pytest.raises(generator.GenerationError, match="unknown schema"):
        generator.collect_types((operation,))


def test_canonical_catalog_mistakes_are_controlled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(generator.CANONICAL_SCHEMA_TYPES, "InvalidFixtureType", object())
    with pytest.raises(generator.GenerationError, match="cannot be inspected"):
        generator._sdk_canonical_schema_contract("InvalidFixtureType")


def test_canonical_manifest_location_is_not_guessed_from_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(generator, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(generator, "MANIFEST_ROOT", tmp_path / "scripts/.generated_methods")
    assert (
        generator._manifest_path(tmp_path / "src/pypokerlost")
        == tmp_path / "scripts/.generated_methods/flat.json"
    )
    assert (
        generator._manifest_path(tmp_path / "other")
        == tmp_path / ".pypokerlost-generated/flat.json"
    )
