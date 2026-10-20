"""Accept the built distribution outside a source checkout without repeating unit tests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pypokerlost_generator.__main__ as generator

import pypokerlost
from pypokerlost import PokerlostClient, PokerlostMethod, PokerlostRequestOptions
from pypokerlost.enums import PokerlostScopes
from pypokerlost.methods import GetToken
from pypokerlost.middleware import PokerlostAuthenticationMiddleware


def main() -> None:
    """Check metadata, typed imports and the actual installed generator entry point."""
    root = Path(__file__).resolve().parents[1]
    expected = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    package = Path(pypokerlost.__file__).resolve().parent
    distribution = importlib.metadata.distribution("pypokerlost")
    assert distribution.version == pypokerlost.__version__ == expected
    assert "site-packages" in package.parts and not package.is_relative_to(root)
    assert not (root / "src").exists()
    assert (package / "py.typed").is_file()
    assert "site-packages" in Path(generator.__file__).resolve().parts
    entrypoint = next(
        item for item in distribution.entry_points if item.name == "pypokerlost-generate"
    )
    assert entrypoint.value == "pypokerlost_generator.__main__:main"
    result = subprocess.run(
        [sys.executable, "-I", "-m", "pypokerlost_generator", "--version"],
        cwd="/tmp",
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert result.stdout.strip() == generator.GENERATOR_VERSION
    for symbol in (
        PokerlostClient,
        PokerlostMethod,
        PokerlostRequestOptions,
        PokerlostScopes,
        GetToken,
        PokerlostAuthenticationMiddleware,
    ):
        assert symbol.__module__.startswith("pypokerlost.")
    built = sorted(Path("/artifacts").glob("*"))
    exported = sorted(Path("/verified-artifacts").glob("*"))
    assert {path.name for path in built} == {path.name for path in exported}
    hashes = {}
    for path in exported:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == hashlib.sha256((Path("/artifacts") / path.name).read_bytes()).hexdigest()
        hashes[path.name] = digest
    assert any(name.endswith(".whl") for name in hashes)
    assert any(name.endswith(".tar.gz") for name in hashes)
    report = {
        "package": expected,
        "artifactSha256": hashes,
        "generator": generator.GENERATOR_VERSION,
        "manifest": generator.MANIFEST_VERSION,
        "outsideCheckout": True,
        "typed": True,
        "installedEntrypoint": True,
    }
    (root / "coverage").mkdir(exist_ok=True)
    (root / "coverage/installed.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
