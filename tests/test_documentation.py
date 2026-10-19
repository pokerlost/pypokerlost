"""Use real temporary Markdown files to validate local paths, anchors and diagnostics."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_documentation as checker


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    monkeypatch.setattr(checker, "REPOSITORY_ROOT", root)
    return root


def test_document_inventory_excludes_private_and_build_directories(repository: Path) -> None:
    (repository / "README.md").write_text("# Main\n")
    (repository / "docs").mkdir()
    (repository / "docs/guide.md").write_text("# Guide\n")
    for name in checker.EXCLUDED_DIRECTORIES:
        directory = repository / name
        directory.mkdir()
        (directory / "ignored.md").write_text("synthetic private/build text\n")
    assert checker._documents() == (repository / "README.md", repository / "docs/guide.md")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" path.md ", "path.md"),
        ("path.md 'Title'", "path.md"),
        ("<space file.md> 'Title'", "space file.md"),
        ("<unclosed", "<unclosed"),
    ],
)
def test_destination_normalization(raw: str, expected: str) -> None:
    assert checker._normalized_destination(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "<>"])
def test_empty_destinations_fail_with_a_diagnostic(repository: Path, raw: str) -> None:
    source = repository / "README.md"
    source.write_text("# Main\n")
    normalized = checker._normalized_destination(raw)
    assert normalized == ""
    assert checker._validate_destination(normalized, source) is not None


def test_code_fences_hide_links_but_preserve_line_positions() -> None:
    value = (
        "before\n```python\n[x](missing.md)\n~~~\nstill code\n```\nafter\n~~~\n[x](missing.md)\n~~~"
    )
    prose = checker._prose_text(value)
    assert prose == "before\n\n\n\n\n\nafter\n\n\n"
    assert prose.count("\n") == value.count("\n")


def test_heading_anchors_handle_duplicates_unicode_and_formatting(repository: Path) -> None:
    document = repository / "guide.md"
    document.write_text("# **Intro**\ntext\n## Intro\n# `Пример` и _тест_!\n```\n# hidden\n```\n")
    assert checker._anchors(document) == {"intro", "intro-1", "пример-и-тест"}


@pytest.mark.parametrize(
    "destination",
    [
        "https://example.invalid/a?q=x#y",
        "http://example.invalid",
        "mailto:person@example.invalid",
        "guide.md",
        "guide.md#intro",
        "guide.md#INTRO",
        "guide.md#intro-1",
        "space%20file.md#example",
        "asset.txt",
        "#main",
    ],
)
def test_valid_links_resolve_without_network(repository: Path, destination: str) -> None:
    source = repository / "README.md"
    source.write_text("# Main\n")
    (repository / "guide.md").write_text("# Intro\n# Intro\n")
    (repository / "space file.md").write_text("# Example\n")
    (repository / "asset.txt").write_text("synthetic asset\n")
    assert checker._validate_destination(destination, source) is None


@pytest.mark.parametrize(
    "destination",
    [
        "https://[broken",
        "https:missing-host",
        "file:///tmp/private",
        "//example.invalid",
        "guide.md?query=value",
        "/absolute.md",
        "../outside.md",
        "%2e%2e/outside.md",
        "missing.md",
        "guide.md#missing",
        "asset.txt#anchor",
    ],
)
def test_invalid_or_escaping_links_are_reported(repository: Path, destination: str) -> None:
    source = repository / "README.md"
    source.write_text("# Main\n")
    (repository / "guide.md").write_text("# Intro\n")
    (repository / "asset.txt").write_text("synthetic asset\n")
    assert checker._validate_destination(destination, source)


def test_link_symlinks_cannot_escape_the_repository(repository: Path) -> None:
    source = repository / "README.md"
    source.write_text("# Main\n")
    outside = repository.parent / "outside.md"
    outside.write_text("# Outside\n")
    (repository / "link.md").symlink_to(outside)
    assert checker._validate_destination("link.md", source)


def test_document_diagnostics_preserve_actual_line_numbers(repository: Path) -> None:
    source = repository / "README.md"
    source.write_text(
        "# Main\n\n[inline](missing.md)\n[reference]: other.md\n```\n[ignored](missing.md)\n```\n"
    )
    errors = checker._validate_document(source)
    assert len(errors) == 2
    assert errors[0].startswith("README.md:3:")
    assert errors[1].startswith("README.md:4:")


def test_workstation_paths_are_forbidden_even_inside_code(repository: Path) -> None:
    source = repository / "README.md"
    source.write_text("# Main\n```\n/home/synthetic/private.md\n```\n")
    errors = checker._validate_document(source)
    assert len(errors) == 1
    assert errors[0].startswith("README.md:3:")
    assert "workstation-specific" in errors[0]


def test_cli_status_is_derived_from_real_documents(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = repository / "README.md"
    source.write_text("# Main\n[local](#main)\n")
    assert checker.main() == 0
    assert "passed for 1 files" in capsys.readouterr().out
    source.write_text("# Main\n[missing](missing.md)\n")
    assert checker.main() == 1
    output = capsys.readouterr().out
    assert "Documentation validation failed" in output
    assert "- README.md:2:" in output
    source.write_text("# Main\n[blank]( )\n")
    assert checker.main() == 1
    assert "link destination must not be empty" in capsys.readouterr().out


def test_documentation_entrypoint_uses_repository_root_outside_cwd(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(Path(checker.__file__))],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Documentation validation passed" in result.stdout
