"""Static handwritten metadata inspection never executes the inspected module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts import generate_methods as generator
from tests.generator_builders import handwritten


def metadata(source: str) -> generator.HandwrittenMethodMetadata:
    return generator._method_metadata_from_source(
        source, "TechnicalProbe", label="synthetic.py", scope_members=generator.SDK_SCOPE_MEMBERS
    )


@pytest.mark.parametrize(
    "source",
    [
        "not valid python (",
        "# No class\n",
        "class Other: pass\n",
        "class TechnicalProbe: pass\n",
        "class TechnicalProbe(Other[int]): pass\n",
        handwritten().replace("ClassVar[tuple[PokerlostScopes, ...] | None]", "str"),
        handwritten().replace(" = None\n", "\n"),
        handwritten(scopes="[]"),
        handwritten(scopes="()"),
        handwritten(scopes="('accounts.self.getMe',)"),
        handwritten(scopes="(OtherScopes.VALUE,)"),
        handwritten(scopes="(PokerlostScopes.UNKNOWN,)"),
        handwritten(
            scopes="(PokerlostScopes.ACCOUNTS_SELF_GET_ME, PokerlostScopes.ACCOUNTS_SELF_GET_ME)"
        ),
        handwritten(
            scopes="(PokerlostScopes.AUTH_CLIENT_MANAGE, PokerlostScopes.ACCOUNTS_SELF_GET_ME)"
        ),
        handwritten().replace(
            "    returning = int",
            "    __scopes__: ClassVar[tuple[PokerlostScopes, ...] | None] = None\n"
            "    returning = int",
        ),
        handwritten().replace("    returning = int\n", ""),
        handwritten().replace('    operation = PokerlostOperation("technicalProbe")\n', ""),
    ],
)
def test_invalid_direct_metadata_is_rejected(source: str) -> None:
    with pytest.raises(generator.GenerationError):
        metadata(source)


def test_none_return_fields_and_irrelevant_assignments_are_inspected_without_import() -> None:
    source = handwritten(
        result="None",
        returning="type(None)",
        field="value: Annotated[tuple[str, ...] | None, Field(repr=False)] = None",
    )
    source = "raise RuntimeError('This module must never be imported')\n" + source
    source += "    helper = alias = 7\n    helper.attribute = 3\n    irrelevant = 1\n"
    result = metadata(source)
    assert result.returning == "None"
    assert result.result_annotation == "None"
    assert result.fields == {"value": ("None|tuple[str,...]", False)}


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (None, True),
        ("None", False),
        ("7", False),
        ("Other()", False),
        ("Field(...)", True),
        ("Field(7)", False),
        ("Field(default=...)", True),
        ("Field(default=None)", False),
        ("Field(default_factory=list)", False),
        ("Field(repr=False)", True),
    ],
)
def test_field_requiredness_matches_explicit_default_semantics(
    expression: str | None, expected: bool
) -> None:
    node = ast.parse(expression, mode="eval").body if expression is not None else None
    assert generator._field_is_required(node) is expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("list[int]", "list[int]"),
        ("datetime.datetime", "datetime.datetime"),
        ("PokerlostAudience", "str"),
        ("tuple[str, ...]", "tuple[str,...]"),
        ("int | str", "int|str"),
        ("Annotated[int, Field()]", "int"),
        ("None", "None"),
    ],
)
def test_annotation_contract_is_normalized(expression: str, expected: str) -> None:
    assert generator._annotation_contract(ast.parse(expression, mode="eval").body) == expected


def test_empty_annotated_shape_is_not_accepted() -> None:
    with pytest.raises(generator.GenerationError, match="value type"):
        generator._annotation_contract(ast.parse("Annotated[()]", mode="eval").body)


@pytest.mark.parametrize(
    "expression",
    [
        "value",
        "Other('technicalProbe')",
        "namespace.PokerlostOperation('technicalProbe')",
        "PokerlostOperation()",
        "PokerlostOperation('one', 'two')",
        "PokerlostOperation(7)",
        "PokerlostOperation(value='technicalProbe')",
    ],
)
def test_operation_constructor_must_be_one_literal(expression: str) -> None:
    with pytest.raises(generator.GenerationError, match="one string literal"):
        generator._call_string(ast.parse(expression, mode="eval").body, "PokerlostOperation")


def test_public_definitions_ignore_private_and_unexported_functions(tmp_path: Path) -> None:
    path = tmp_path / "types.py"
    path.write_text(
        "class Public: pass\nclass _Private: pass\n"
        "type Alias = str\ntype _Hidden = int\n"
        "def helper(): pass\nasync def other(): pass\n"
    )
    assert generator._defined_public_types(path) == ("Public", "Alias")
    assert generator._defined_methods(path) == ()


@pytest.mark.parametrize("kind", ["wrongClass", "wrongModule", "duplicate"])
def test_handwritten_inventory_rejects_inconsistent_names_and_duplicates(
    tmp_path: Path, kind: str
) -> None:
    content = handwritten()
    filename = "technical_probe.py"
    if kind == "wrongClass":
        content = content.replace("class TechnicalProbe", "class Other")
    elif kind == "wrongModule":
        filename = "other.py"
    else:
        content += "\n" + handwritten()
    (tmp_path / filename).write_text(content)
    with pytest.raises(generator.GenerationError):
        generator._validate_handwritten_methods(tmp_path, scope_members=generator.SDK_SCOPE_MEMBERS)
