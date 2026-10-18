"""Actual file generation, ownership, check-mode drift and compiled SDK behavior."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import pypokerlost
from scripts import generate_methods as generator
from tests.generator_builders import document, handwritten, object_schema


def source(operation: str = "technicalProbe") -> generator.SourceDocument:
    return generator.parse_document(document(operation), label="synthetic.json")


def files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


def test_write_check_and_stale_cleanup_preserve_unowned_files(tmp_path: Path) -> None:
    output = tmp_path / "pypokerlost"
    contract = source()
    with pytest.raises(generator.GenerationError, match="out of date"):
        generator.generate((contract,), output=output, check=True)
    assert not output.exists()
    assert (
        generator.generate((contract,), output=output, check=False)
        == "generated 1 operations and 0 flat types"
    )
    assert (
        generator.generate((contract,), output=output, check=True)
        == "1 operations and 0 types are up to date"
    )
    marker = output / "types/owner_notes.txt"
    marker.write_text("application-owned bytes\n")
    manifest = tmp_path / ".pypokerlost-generated/flat.json"
    owned = json.loads(manifest.read_text())
    assert owned["manifest_version"] == 4
    assert owned["generator_version"] == generator.GENERATOR_VERSION
    assert owned["files"] == [
        "methods/__init__.py",
        "methods/technical_probe.py",
        "types/__init__.py",
    ]
    assert owned["sources"][0]["source_sha256"] == contract.source_sha256
    before = files(tmp_path)
    generator.generate((contract,), output=output, check=False)
    assert files(tmp_path) == before
    (output / "methods/technical_probe.py").write_text(generator.GENERATED_HEADER + "# drift\n")
    with pytest.raises(generator.GenerationError, match=r"technical_probe\.py"):
        generator.generate((contract,), output=output, check=True)
    generator.generate((source("technicalSecond"),), output=output, check=False)
    assert not (output / "methods/technical_probe.py").exists()
    assert (output / "methods/technical_second.py").exists()
    assert marker.read_text() == "application-owned bytes\n"


def test_compatible_handwritten_method_remains_outside_manifest_ownership(tmp_path: Path) -> None:
    output = tmp_path / "pypokerlost"
    methods = output / "methods"
    methods.mkdir(parents=True)
    method = methods / "technical_probe.py"
    content = handwritten()
    method.write_text(content)
    generator.generate((source(),), output=output, check=False)
    assert method.read_text() == content
    manifest = json.loads((tmp_path / ".pypokerlost-generated/flat.json").read_text())
    assert "methods/technical_probe.py" not in manifest["files"]
    assert "TechnicalProbe" in (methods / "__init__.py").read_text()
    generator.generate((source(),), output=output, check=True)


@pytest.mark.parametrize("kind", ["generic", "returning", "fields", "scopes"])
def test_incompatible_handwritten_contract_is_not_overwritten(tmp_path: Path, kind: str) -> None:
    output = tmp_path / "pypokerlost"
    (output / "methods").mkdir(parents=True)
    options = (
        {"result": "str"}
        if kind == "generic"
        else {"returning": "str"}
        if kind == "returning"
        else {"field": "unexpected: int"}
        if kind == "fields"
        else {"scopes": "(PokerlostScopes.ACCOUNTS_SELF_GET_ME,)"}
    )
    (output / "methods/technical_probe.py").write_text(handwritten(**options))
    before = files(tmp_path)
    with pytest.raises(generator.GenerationError, match=r"does not match|do not match"):
        generator.generate((source(),), output=output, check=False)
    assert files(tmp_path) == before


def test_stale_file_claimed_by_owner_blocks_all_writes(tmp_path: Path) -> None:
    output = tmp_path / "pypokerlost"
    generator.generate((source(),), output=output, check=False)
    old = output / "methods/technical_probe.py"
    old.write_text("# Handwritten ownership restored; no generated header\n")
    before = files(tmp_path)
    with pytest.raises(generator.GenerationError, match="refusing to remove"):
        generator.generate((source("technicalSecond"),), output=output, check=False)
    assert files(tmp_path) == before


@pytest.mark.parametrize("unsafe", ["../outside.py", "/absolute.py", "types/not_python.txt"])
def test_unsafe_previous_manifest_cannot_address_other_files(tmp_path: Path, unsafe: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"files": [unsafe]}))
    with pytest.raises(generator.GenerationError, match="unsafe path"):
        generator._previous_owned_files(path)


def test_stale_missing_file_and_old_facade_do_not_delete_unowned_data(tmp_path: Path) -> None:
    output = tmp_path / "pypokerlost"
    manifest = tmp_path / ".pypokerlost-generated/flat.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"files": ["methods/missing.py", "old/__init__.py"]}))
    (output / "old").mkdir(parents=True)
    owner = output / "old/__init__.py"
    owner.write_text("# Owner data\n")
    generator.generate((source(),), output=output, check=False)
    assert owner.read_text() == "# Owner data\n"


def test_cli_file_version_and_safe_failure(tmp_path: Path) -> None:
    runner = CliRunner()
    version = runner.invoke(generator.app, ["--version"])
    assert version.exit_code == 0
    assert version.stdout.strip() == generator.GENERATOR_VERSION
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(document()))
    output = tmp_path / "pypokerlost"
    arguments = ["file", str(path), "--output", str(output)]
    assert runner.invoke(generator.app, arguments).exit_code == 0
    assert runner.invoke(generator.app, [*arguments, "--check"]).exit_code == 0
    path.write_text('{"synthetic-private-input":')
    result = runner.invoke(generator.app, arguments)
    assert result.exit_code == 1
    assert "not valid JSON" in result.stderr
    assert "synthetic-private-input" not in result.stderr
    assert runner.invoke(generator.app, ["file", str(tmp_path / "missing.json")]).exit_code == 2


def test_cli_main_runs_from_another_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(Path(generator.__file__)), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == generator.GENERATOR_VERSION


def test_generated_sdk_imports_and_executes_actual_typed_method(tmp_path: Path) -> None:
    root = tmp_path / "generated-sdk"
    output = root / "pypokerlost"
    shutil.copytree(
        Path(pypokerlost.__file__).parent,
        output,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    owned_method = (output / "methods/get_token.py").read_bytes()
    raw = document(payload=object_schema({"value": {"type": "integer"}}, ["value"]))
    parsed = generator.parse_document(raw, label="synthetic.json")
    generator.generate((parsed,), output=output, check=False)
    assert (output / "methods/get_token.py").read_bytes() == owned_method
    generator.generate((parsed,), output=output, check=True)
    # Generated artifact code differs from the canonical package and must not inflate
    # its coverage denominator. Actual SDK subprocess tests retain coverage normally.
    environment = os.environ.copy()
    environment.pop("COVERAGE_PROCESS_CONFIG", None)
    environment.pop("COVERAGE_PROCESS_START", None)
    code = r"""
import asyncio, json
import httpx
from pypokerlost import PokerlostClient
from pypokerlost.methods import TechnicalProbe, GetToken
from pypokerlost.session import HttpxSession
requests = []
def respond(request):
    requests.append(request)
    assert json.loads(request.content) == {"payload": {"value": 7}}
    assert "authorization" not in request.headers
    return httpx.Response(200, json={"ok": True, "result": 17})
async def main():
    session = HttpxSession()
    session._http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    async with PokerlostClient(session=session) as client:
        method = TechnicalProbe(value=7)
        assert method.__scopes__ is None
        assert await client(method) == 17
    assert session._http_client is None
asyncio.run(main())
assert len(requests) == 1
assert GetToken.operation == "getToken"
print("generated SDK behavior passed")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "generated SDK behavior passed"
