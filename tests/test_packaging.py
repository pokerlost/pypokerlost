"""Build archives with synthetic local metadata and ensure it cannot be shipped."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {".aws", ".agents", ".codex", ".serena", ".local", "backups", ".env.private"}

ARCHIVE_ARTIFACTS = {".coverage", ".coverage.parallel", "core.1234"}


@pytest.mark.parametrize("aws_kind", ["file", "directory"])
def test_locked_backend_excludes_private_inputs_without_git(tmp_path: Path, aws_kind: str) -> None:
    root = tmp_path / "package"
    root.mkdir()
    for name in ("pyproject.toml", "README.md", ".gitignore"):
        shutil.copy2(REPOSITORY / name, root / name)
    package = root / "pypokerlost"
    package.mkdir()
    (package / "__init__.py").write_text('"""Synthetic packaging-policy fixture."""\n')
    for name in PRIVATE_PARTS - {".env.private", ".aws"}:
        (root / name).mkdir()
        (root / name / "fixture").write_text("synthetic-not-credentials\n")
    if aws_kind == "directory":
        (root / ".aws").mkdir()
        (root / ".aws/fixture").write_text("synthetic-not-credentials\n")
    else:
        (root / ".aws").write_text("synthetic-not-credentials\n")
    (root / ".env.private").write_text("SYNTHETIC=private-marker\n")
    (root / ".env.example").write_text("SYNTHETIC=example\n")
    for name in ARCHIVE_ARTIFACTS:
        marker = root / name
        marker.write_text("synthetic local build artifact\n")
        marker.chmod(0)
    (root / ".coveragerc").write_text("[run]\nbranch = true\n")
    (package / "core").mkdir()
    (package / "core/retained.py").write_text("VALUE = 1\n")
    environment = os.environ.copy()
    # This fixture's package differs from the canonical SDK; measure archive
    # membership instead of attributing its source to SDK runtime coverage.
    environment.pop("COVERAGE_PROCESS_CONFIG", None)
    environment.pop("COVERAGE_PROCESS_START", None)
    result = subprocess.run(
        [sys.executable, "-m", "hatchling", "build"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with tarfile.open(next((root / "dist").glob("*.tar.gz"))) as archive:
        sdist = archive.getnames()
    with zipfile.ZipFile(next((root / "dist").glob("*.whl"))) as archive:
        wheel = archive.namelist()
    for name in (*sdist, *wheel):
        assert not (PRIVATE_PARTS | ARCHIVE_ARTIFACTS).intersection(Path(name).parts), name
    assert any(name.endswith("/pypokerlost/__init__.py") for name in sdist)
    assert "pypokerlost/__init__.py" in wheel
    assert "pypokerlost/core/retained.py" in wheel
    assert any(name.endswith("/.coveragerc") for name in sdist)
    assert any(name.endswith("/.env.example") for name in sdist)
